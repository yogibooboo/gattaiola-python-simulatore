import numpy as np
from scipy.signal import find_peaks
import struct
import matplotlib.pyplot as plt
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

BYTES_NOTI = [0x54, 0xDD, 0x25, 0x3C, 0x3D, 0xE1, 0x01, 0x80, 0x1C, 0xC9]

# Variabile globale per tracciare la finestra di confronto
_confronto_window = None

def genera_sequenza_bit(bytes_noti):
    print("Debug: Generazione sequenza bit...")
    try:
        bits = [0] * 10 + [1]
        for byte in bytes_noti:
            for i in range(8):
                bits.append((byte >> i) & 1)
            bits.append(1)
        print(f"Debug: Lunghezza sequenza bit: {len(bits)}")
        print(f"Debug: Primi 20 bit: {bits[:20]}")
        return bits
    except Exception as e:
        print(f"Debug: Errore in genera_sequenza_bit: {e}")
        raise

def genera_segnale_riferimento(sequenza_bit, debug_plot=False):
    print("Debug: Generazione segnale di riferimento...")
    try:
        campioni_per_bit = 32
        segnale = np.zeros(len(sequenza_bit) * campioni_per_bit)
        polarita = 1  # Polarità iniziale
        for i, bit in enumerate(sequenza_bit):
            inizio = i * campioni_per_bit
            if i == 0:
                current_polarita = polarita
            else:
                current_polarita = -ultima_polarita
            if bit == 1:
                segnale[inizio:inizio + campioni_per_bit] = current_polarita
                ultima_polarita = current_polarita
            else:
                segnale[inizio:inizio + campioni_per_bit // 2] = current_polarita
                segnale[inizio + campioni_per_bit // 2:inizio + campioni_per_bit] = -current_polarita
                ultima_polarita = -current_polarita
        # segnale = segnale / np.linalg.norm(segnale) if np.linalg.norm(segnale) != 0 else segnale
        print(f"Debug: Lunghezza segnale riferimento: {len(segnale)}")
        print(f"Debug: Primi 100 campioni riferimento: {segnale[:100]}")
        if debug_plot:
            plt.figure()
            plt.plot(segnale, label="Segnale di Riferimento")
            plt.title("Segnale di Riferimento (BMC, 32 campioni/bit)")
            for i in range(0, len(segnale), campioni_per_bit):
                plt.axvline(i, color='black', linestyle='--', linewidth=0.5)
                plt.axvline(i + campioni_per_bit // 2, color='gray', linestyle=':', linewidth=0.3)
            plt.legend()
            plt.show()
        return segnale
    except Exception as e:
        print(f"Debug: Errore in genera_segnale_riferimento: {e}")
        raise

def correlazione_con_sequenza_nota(percorso_file, bytes_noti, status_label, ax1, risultato_text, segnale_filtrato=None):
    global _confronto_window
    print("Debug: Inizio funzione correlazione_con_sequenza_nota...")
    try:
        status_label.config(text="Stato: Correlazione in corso...")
        if segnale_filtrato is None:
            print("Debug: Lettura file .bin...")
            with open(percorso_file, "rb") as f:
                data = f.read()
            segnale = np.array(struct.unpack("<" + "h" * (len(data) // 2), data))
            print(f"Debug: Segnale letto da file, lunghezza: {len(segnale)}")
        else:
            print("Debug: Uso segnale filtrato...")
            segnale = np.array(segnale_filtrato, dtype=np.float64)
            print(f"Debug: Lunghezza segnale filtrato: {len(segnale)}")
            print(f"Debug: Primi 50 campioni segnale filtrato: {segnale[:50]}")

        print(f"Debug: Lunghezza segnale: {len(segnale)}")
        segnale = segnale - np.mean(segnale)
        segnale = segnale / np.linalg.norm(segnale) if np.linalg.norm(segnale) != 0 else segnale

        print("Debug: Generazione sequenza bit e riferimento...")
        bits = genera_sequenza_bit(bytes_noti)
        riferimento = genera_segnale_riferimento(bits, debug_plot=False)

        print("Debug: Calcolo correlazione...")
        correlazione = np.correlate(segnale, riferimento, mode='full')
        norm = np.sqrt(np.sum(segnale**2) * np.sum(riferimento**2))
        correlazione = correlazione / norm if norm != 0 else correlazione
        print(f"Debug: Lunghezza correlazione: {len(correlazione)}, max: {np.max(np.abs(correlazione)):.3f}")

        soglia = 0.1
        print(f"Debug: Ricerca picchi con soglia {soglia}...")
        picchi_pos, props_pos = find_peaks(correlazione, height=soglia)
        picchi_neg, props_neg = find_peaks(-correlazione, height=soglia)
        print(f"Debug: Picchi positivi: {len(picchi_pos)}, Picchi negativi: {len(picchi_neg)}")

        risultati = []
        for idx in picchi_pos:
            risultati.append((correlazione[idx], idx, idx // 32))
        for idx in picchi_neg:
            risultati.append((-correlazione[idx], idx, idx // 32))
        risultati.sort(key=lambda x: abs(x[0]), reverse=True)
        print(f"Debug: Totale picchi trovati: {len(risultati)}")

        # Determina il massimo picco per il grafico di confronto
        idx_max = risultati[0][1] if risultati else 774  # Fallback a 774 se nessun picco
        print(f"Debug: Massimo picco al campione {idx_max} (bit {idx_max // 32})")

        print(f"Debug: Confronto segnale filtrato e riferimento vicino a {idx_max}...")
        inizio = idx_max - 50
        fine = idx_max + 3232 + 50
        if inizio >= 0 and fine < len(segnale):
            segmento_segnale = segnale[inizio:fine]
            segmento_segnale = segmento_segnale / np.linalg.norm(segmento_segnale) if np.linalg.norm(segmento_segnale) != 0 else segmento_segnale
            correlazione_segmento = np.correlate(segmento_segnale, riferimento, mode='valid')
            print(f"Debug: Correlazione segmento, max: {np.max(np.abs(correlazione_segmento)):.3f}")

            if _confronto_window is None or not _confronto_window.winfo_exists():
                _confronto_window = tk.Toplevel()
                _confronto_window.title(f"Confronto Segnale e Riferimento (campione {idx_max})")
                frame = tk.Frame(_confronto_window)
                frame.pack(fill=tk.BOTH, expand=True)

                fig_confronto, ax_confronto = plt.subplots(figsize=(12, 6))
                ax_confronto.plot(segmento_segnale, label=f"Segnale di ingresso (vicino a {idx_max})", alpha=0.7)
                ax_confronto.plot(riferimento, label="Segnale di riferimento", alpha=0.7)
                for i in range(0, len(riferimento), 32):
                    ax_confronto.axvline(i, color='black', linestyle='--', linewidth=0.5)
                    ax_confronto.axvline(i + 16, color='gray', linestyle=':', linewidth=0.3)
                ax_confronto.set_title(f"Confronto Segnale di Ingresso e Riferimento (campione {idx_max})")
                ax_confronto.legend()

                canvas = FigureCanvasTkAgg(fig_confronto, master=frame)
                canvas.draw()
                canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

                toolbar = NavigationToolbar2Tk(canvas, frame)
                toolbar.update()
                canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

                _confronto_window.protocol("WM_DELETE_WINDOW", lambda: _confronto_window.destroy())
                print("Debug: Finestra di confronto creata")
            else:
                print("Debug: Finestra di confronto già esistente")
            print("Debug: Confronto completato, proseguo con correlazione completa...")
        else:
            print(f"Debug: Finestra non valida per il confronto (inizio: {inizio}, fine: {fine})")

        print("Debug: Aggiornamento risultato_text...")
        risultato_text.delete(1.0, tk.END)
        if risultati:
            max_conf = abs(risultati[0][0])
            risultato_text.insert(tk.END, f"Confidenza massima: {max_conf:.3f}\n")
            risultato_text.insert(tk.END, "Corrispondenze trovate:\n")
            for conf, idx, bit in risultati:
                risultato_text.insert(tk.END, f"Confidenza {conf:.3f} al bit {bit} (campione {idx})\n")
        else:
            risultato_text.insert(tk.END, f"Nessuna corrispondenza sopra la soglia {soglia}\n")
            risultato_text.insert(tk.END, f"Valore massimo correlazione: {np.max(np.abs(correlazione)):.3f}\n")

        print("Debug: Disegno curva di correlazione in ROSSO...")
        ax2 = ax1.twinx()
        ax2.clear()
        ax2.plot(correlazione, 'r-', label='Correlazione', alpha=0.5)
        for idx in picchi_pos:
            ax2.plot(idx, correlazione[idx], 'kx', label='Picco positivo' if idx == picchi_pos[0] else "", markersize=10)
        for idx in picchi_neg:
            ax2.plot(idx, correlazione[idx], 'kx', label='Picco negativo' if idx == picchi_neg[0] else "", markersize=10)
        ax2.axhline(soglia, color='g', linestyle='--', label='Soglia positiva')
        ax2.axhline(-soglia, color='g', linestyle='--', label='Soglia negativa')
        ax2.set_ylabel('Correlazione')
        ax2.legend(loc='upper right')
        ax2.set_ylim(-1, 1)
        ax1.figure.canvas.draw()
        ax1.figure.canvas.flush_events()
        print("Debug: Grafico aggiornato")

        status_label.config(text="Stato: Correlazione completata")
        print("Debug: Correlazione completata")
    except Exception as e:
        print(f"Debug: Errore in correlazione_con_sequenza_nota: {e}")
        status_label.config(text=f"Errore: Correlazione fallita: {e}")
        risultato_text.delete(1.0, tk.END)
        risultato_text.insert(tk.END, f"Errore: {e}\n")