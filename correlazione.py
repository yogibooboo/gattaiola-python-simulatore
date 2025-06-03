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

import numpy as np
import tkinter as tk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from scipy.signal import find_peaks
import struct

import numpy as np
import tkinter as tk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from scipy.signal import find_peaks
import struct
import time

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

        current_peak_idx = 0  # Indice del picco corrente
        idx_max = risultati[current_peak_idx][1] if risultati else 774
        print(f"Debug: Massimo picco al campione {idx_max} (bit {idx_max // 32})")

        offset = 0
        lunghezza_riferimento = len(riferimento)
        print(f"Debug: Confronto segnale filtrato e riferimento vicino a {idx_max}...")
        inizio = max(0, idx_max - lunghezza_riferimento)
        fine = inizio + lunghezza_riferimento

        # Inizializza i limiti x e y come variabili persistenti
        xlim = (inizio, fine)  # Limiti x iniziali
        ylim = (-1.5, 1.5)     # Limiti y iniziali
        previous_offset = offset  # Traccia l'offset precedente

        if inizio >= 0 and fine < len(segnale):
            segmento_segnale = segnale[inizio:fine]
            segmento_segnale = segmento_segnale / np.linalg.norm(segmento_segnale) if np.linalg.norm(segmento_segnale) != 0 else segmento_segnale
            print(f"Debug: Segmento segnale, lunghezza: {len(segmento_segnale)}")

            if _confronto_window is None or not _confronto_window.winfo_exists():
                _confronto_window = tk.Toplevel()
                _confronto_window.title(f"Confronto Segnale e Riferimento (inizio: {inizio})")
                frame = tk.Frame(_confronto_window)
                frame.pack(fill=tk.BOTH, expand=True)

                fig_confronto, ax_confronto = plt.subplots(figsize=(12, 6))
                canvas = FigureCanvasTkAgg(fig_confronto, master=frame)
                canvas.draw()
                canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

                toolbar = NavigationToolbar2Tk(canvas, frame)
                toolbar.update()
                canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

                button_frame = tk.Frame(_confronto_window)
                button_frame.pack(side=tk.BOTTOM, fill=tk.X)
                tk.Button(button_frame, text="Sposta Sinistra", command=lambda: sposta_sinistra()).pack(side=tk.LEFT, padx=5, pady=5)
                tk.Button(button_frame, text="Sposta Destra", command=lambda: sposta_destra()).pack(side=tk.LEFT, padx=5, pady=5)
                tk.Button(button_frame, text="Picco Precedente", command=lambda: seleziona_picco_precedente()).pack(side=tk.LEFT, padx=5, pady=5)
                tk.Button(button_frame, text="Picco Successivo", command=lambda: seleziona_picco_successivo()).pack(side=tk.LEFT, padx=5, pady=5)
                tk.Label(button_frame, text="Campione Iniziale:").pack(side=tk.LEFT, padx=5, pady=5)
                entry_inizio = tk.Entry(button_frame, width=10)
                entry_inizio.pack(side=tk.LEFT, padx=5, pady=5)
                tk.Button(button_frame, text="Imposta Inizio", command=lambda: imposta_inizio(entry_inizio.get())).pack(side=tk.LEFT, padx=5, pady=5)

                _confronto_window.protocol("WM_DELETE_WINDOW", lambda: _confronto_window.destroy())
                print("Debug: Finestra di confronto creata")
            else:
                print("Debug: Finestra di confronto già esistente")
                for widget in _confronto_window.winfo_children():
                    if isinstance(widget, tk.Frame):
                        for child in widget.winfo_children():
                            if isinstance(child, tk.Canvas):
                                canvas = child.master
                                fig_confronto = canvas.figure
                                ax_confronto = fig_confronto.axes[0]
                                break

            def aggiorna_grafico(offset_attuale):
                nonlocal xlim, ylim, previous_offset, current_peak_idx, risultati, idx_max

                # Salva i limiti correnti per catturare lo zoom manuale
                current_xlim = ax_confronto.get_xlim()
                current_ylim = ax_confronto.get_ylim()

                # Usa i limiti salvati (che riflettono lo zoom manuale) per l'asse y
                if current_ylim != (0, 1):  # Evita valori di default di Matplotlib
                    ylim = current_ylim

                inizio_offset = max(0, idx_max - lunghezza_riferimento + offset_attuale)
                fine_offset = inizio_offset + lunghezza_riferimento
                if fine_offset > len(segnale):
                    fine_offset = len(segnale)
                    inizio_offset = max(0, fine_offset - lunghezza_riferimento)
                segmento_segnale_offset = segnale[inizio_offset:fine_offset]
                segmento_segnale_offset = segmento_segnale_offset / np.linalg.norm(segmento_segnale_offset) if np.linalg.norm(segmento_segnale_offset) != 0 else segmento_segnale_offset
                print(f"Debug: aggiorna_grafico: inizio_offset={inizio_offset}, fine_offset={fine_offset}")

                ax_confronto.clear()
                indici_assoluti = np.arange(inizio_offset, fine_offset)
                ax_confronto.plot(indici_assoluti, segmento_segnale_offset, label=f"Segnale di ingresso (offset: {offset_attuale})", alpha=0.7)
                ax_confronto.plot(indici_assoluti, riferimento, label="Segnale di riferimento", alpha=0.7)
                for i in range(0, lunghezza_riferimento, 32):
                    ax_confronto.axvline(inizio_offset + i, color='black', linestyle='--', linewidth=0.5)
                    ax_confronto.axvline(inizio_offset + i + 16, color='gray', linestyle=':', linewidth=0.3)
                ax_confronto.set_title(f"Confronto Segnale di Ingresso e Riferimento (inizio: {inizio_offset})")
                ax_confronto.set_xlabel("Indici del segnale di ingresso")
                ax_confronto.set_ylabel("Ampiezza")
                ax_confronto.legend()

                # MODIFICA: Aggiorna i limiti x in base a inizio_offset e fine_offset
                # Calcola lo spostamento solo se c'è uno zoom manuale
                if current_xlim != (0, 1) and current_xlim != (inizio - (offset_attuale - previous_offset), fine - (offset_attuale - previous_offset)):
                    lunghezza_zoom = current_xlim[1] - current_xlim[0]
                    shift = offset_attuale - previous_offset
                    new_xlim = (current_xlim[0] + shift, current_xlim[0] + shift + lunghezza_zoom)
                else:
                    new_xlim = (inizio_offset, fine_offset)

                # Assicurati che i nuovi limiti siano validi
                if new_xlim[0] >= 0 and new_xlim[1] <= len(segnale):
                    ax_confronto.set_xlim(new_xlim)
                else:
                    ax_confronto.set_xlim(inizio_offset, fine_offset)

                # Ripristina i limiti y
                ax_confronto.set_ylim(ylim)

                # Aggiorna i limiti salvati
                xlim = ax_confronto.get_xlim()
                ylim = ax_confronto.get_ylim()
                previous_offset = offset_attuale  # Aggiorna l'offset precedente

                print(f"Debug: Limiti y: {ax_confronto.get_ylim()}")
                print(f"Debug: Limiti x: {ax_confronto.get_xlim()}")
                canvas.draw()

            def sposta_sinistra():
                nonlocal offset, previous_offset
                offset += 1
                print(f"Debug: Offset aggiornato: {offset}")
                aggiorna_grafico(offset)

            def sposta_destra():
                nonlocal offset, previous_offset
                offset -= 1
                print(f"Debug: Offset aggiornato: {offset}")
                aggiorna_grafico(offset)

            def seleziona_picco_precedente():
                nonlocal current_peak_idx, idx_max, offset, previous_offset
                if current_peak_idx > 0:
                    current_peak_idx -= 1
                    idx_max = risultati[current_peak_idx][1]
                    print(f"Debug: Picco precedente selezionato, idx_max={idx_max}, current_peak_idx={current_peak_idx}")
                    # Resetta l'offset per allineare il nuovo picco
                    offset = 0
                    previous_offset = 0  # MODIFICA: Resetta anche previous_offset
                    aggiorna_grafico(offset)
                else:
                    print("Debug: Nessun picco precedente disponibile")

            def seleziona_picco_successivo():
                nonlocal current_peak_idx, idx_max, offset, previous_offset
                if current_peak_idx < len(risultati) - 1:
                    current_peak_idx += 1
                    idx_max = risultati[current_peak_idx][1]
                    print(f"Debug: Picco successivo selezionato, idx_max={idx_max}, current_peak_idx={current_peak_idx}")
                    # Resetta l'offset per allineare il nuovo picco
                    offset = 0
                    previous_offset = 0  # MODIFICA: Resetta anche previous_offset
                    aggiorna_grafico(offset)
                else:
                    print("Debug: Nessun picco successivo disponibile")

            def imposta_inizio(valore):
                nonlocal offset, idx_max, previous_offset
                try:
                    nuovo_inizio = int(valore)
                    if nuovo_inizio >= 0 and nuovo_inizio <= len(segnale) - lunghezza_riferimento:
                        # Calcola il nuovo offset in base al nuovo inizio
                        offset = nuovo_inizio - (idx_max - lunghezza_riferimento)
                        previous_offset = offset  # MODIFICA: Sincronizza previous_offset
                        print(f"Debug: Campione iniziale impostato a {nuovo_inizio}, nuovo offset={offset}")
                        aggiorna_grafico(offset)
                    else:
                        print(f"Debug: Valore non valido per il campione iniziale: {nuovo_inizio}")
                except ValueError:
                    print("Debug: Inserire un valore numerico valido")

            aggiorna_grafico(offset)
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