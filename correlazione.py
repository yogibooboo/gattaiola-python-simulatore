import numpy as np
from scipy.signal import find_peaks
import struct
import matplotlib.pyplot as plt
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import analisiESP32

BYTES_NOTI = [0x54, 0xDD, 0x25, 0x3C, 0x3D, 0xE1, 0x01, 0x80, 0x1C, 0xC9]

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
        return bits
    except Exception as e:
        print(f"Errore in genera_sequenza_bit: {e}")
        raise

def genera_segnale_riferimento(sequenza_bit, debug_plot=False):
    print("Debug: Generazione segnale di riferimento...")
    try:
        campioni_per_bit = 32
        segnale = np.zeros(len(sequenza_bit) * campioni_per_bit)
        polarita = 1
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
        print(f"Debug: Lunghezza segnale riferimento: {len(segnale)}")
        if debug_plot:
            plt.figure()
            plt.plot(segnale, label="Segnale di Riferimento")
            plt.title("Segnale di Riferimento (BMC, 32 campioni/bit)")
            plt.legend()
            plt.show()
        return segnale
    except Exception as e:
        print(f"Errore in genera_segnale_riferimento: {e}")
        raise

def correlazione_con_sequenza_nota(percorso_file, bytes_noti, status_label, ax1, risultato_text, segnale_filtrato=None, media_scorrevole_var=None):
    global _confronto_window
    print("Debug: Inizio correlazione_con_sequenza_nota...")
    try:
        status_label.config(text="Stato: Correlazione in corso...")
        if segnale_filtrato is None or (media_scorrevole_var and not media_scorrevole_var.get()):
            with open(percorso_file, "rb") as f:
                data = f.read()
            segnale = np.array(struct.unpack("<" + "h" * (len(data) // 2), data))
        else:
            segnale = np.array(segnale_filtrato, dtype=np.float64)

        segnale = segnale - np.mean(segnale)
        norm_segnale = np.linalg.norm(segnale)
        segnale = segnale / norm_segnale if norm_segnale != 0 else segnale

        bits = genera_sequenza_bit(bytes_noti)
        riferimento = genera_segnale_riferimento(bits)

        correlazione = np.correlate(segnale, riferimento, mode='full')
        norm = np.sqrt(np.sum(segnale**2) * np.sum(riferimento**2))
        correlazione = correlazione / norm if norm != 0 else correlazione

        soglia = 0.1
        picchi_pos, _ = find_peaks(correlazione, height=soglia)
        picchi_neg, _ = find_peaks(-correlazione, height=soglia)

        risultati = [(correlazione[idx], idx, idx // 32) for idx in picchi_pos]
        risultati += [(-correlazione[idx], idx, idx // 32) for idx in picchi_neg]
        risultati.sort(key=lambda x: abs(x[0]), reverse=True)

        current_peak_idx = 0
        idx_max = risultati[0][1] if risultati else 774
        offset = 0
        lunghezza_riferimento = len(riferimento)
        inizio = max(0, idx_max - lunghezza_riferimento)
        fine = inizio + lunghezza_riferimento

        xlim = (inizio, fine)
        ylim_segnale = (-1.5, 1.5)
        ylim_corr = None
        previous_offset = offset
        previous_idx_max = idx_max

        if inizio >= 0 and fine <= len(segnale):
            segmento_segnale = segnale[inizio:fine]
            norm_segmento = np.linalg.norm(segmento_segnale)
            segmento_segnale = segmento_segnale / norm_segmento if norm_segmento != 0 else segmento_segnale

            def aggiorna_grafico(offset_attuale):
                nonlocal current_peak_idx, idx_max, offset, previous_offset, xlim, ylim_segnale, ylim_corr, previous_idx_max
                print(f"Debug: Aggiorna grafico, modalità: {'Segnale' if mostra_var.get() == 0 else 'Correlazione ESP32'}, offset: {offset_attuale}, idx_max: {idx_max}")
                # Salva i limiti correnti
                current_xlim = ax_confronto.get_xlim()
                current_ylim = ax_confronto.get_ylim()

                # Calcola il nuovo segmento
                inizio_offset = max(0, idx_max - lunghezza_riferimento + offset_attuale)
                fine_offset = min(inizio_offset + lunghezza_riferimento, len(segnale))
                segmento_segnale_offset = segnale[inizio_offset:fine_offset]
                norm_segmento_offset = np.linalg.norm(segmento_segnale_offset)
                if norm_segmento_offset != 0:
                    segmento_segnale_offset = segmento_segnale_offset / norm_segmento_offset
                else:
                    print("Debug: Norm segmento_segnale_offset è zero, mantengo dati non normalizzati")
                print(f"Debug: Segmento segnale offset, min: {np.min(segmento_segnale_offset)}, max: {np.max(segmento_segnale_offset)}")
                indici_assoluti = np.arange(inizio_offset, fine_offset)

                # Gestisci i limiti x
                if current_xlim != (0, 1) and previous_idx_max == idx_max:
                    # Preserva lo zoom traslando i limiti x
                    zoom_width = current_xlim[1] - current_xlim[0]
                    delta_offset = offset_attuale - previous_offset
                    new_xlim = (current_xlim[0] + delta_offset, current_xlim[1] + delta_offset)
                    # Limita i nuovi limiti x per non uscire dal segnale
                    new_xlim = (max(0, new_xlim[0]), min(len(segnale), new_xlim[0] + zoom_width))
                    xlim = new_xlim
                else:
                    # Reset xlim al nuovo intervallo per cambio picco o inizio
                    xlim = (inizio_offset, fine_offset)
                
                # Salva i limiti y se aggiornati
                if current_ylim != (0, 1) and mostra_var.get() == 0:
                    ylim_segnale = current_ylim

                print(f"Debug: Limiti x: {xlim}")

                # Rimuovi eventuali assi secondari e resetta l’asse principale
                for ax in ax_confronto.figure.axes:
                    if ax != ax_confronto:
                        ax.remove()
                ax_confronto.clear()

                if mostra_var.get() == 0:  # Modalità Segnale
                    print("Debug: Plottando modalità Segnale...")
                    ax_confronto.plot(indici_assoluti, segmento_segnale_offset, label="Segnale di ingresso", color='blue', alpha=0.7)
                    ax_confronto.plot(indici_assoluti, riferimento[:len(indici_assoluti)], label="Segnale di riferimento", color='orange', alpha=0.7)
                    for i in range(0, len(indici_assoluti), 32):
                        ax_confronto.axvline(indici_assoluti[i], color='gray', linestyle='--', alpha=0.5)
                    ax_confronto.set_title(f"Confronto Segnale (inizio: {inizio_offset})")
                    ax_confronto.set_ylabel("Ampiezza")
                    # Imposta limiti y dinamici
                    if np.any(segmento_segnale_offset):
                        segn_min, segn_max = np.min(segmento_segnale_offset), np.max(segmento_segnale_offset)
                        ylim_segnale = (segn_min - 0.1 * (segn_max - segn_min), segn_max + 0.1 * (segn_max - segn_min))
                    ax_confronto.set_ylim(ylim_segnale)
                    print(f"Debug: Limiti y Segnale: {ylim_segnale}")
                else:  # Modalità Correlazione ESP32
                    print("Debug: Plottando modalità Correlazione ESP32...")
                    correlazione32 = analisiESP32.get_correlazione32()
                    picchi32 = analisiESP32.get_picchi32()
                    bits32 = analisiESP32.get_bits32()
                    if correlazione32 is not None and picchi32 is not None and bits32 is not None:
                        segmento_correlazione = correlazione32[inizio_offset:fine_offset]
                        print(f"Debug: Segmento correlazione, min: {np.min(segmento_correlazione)}, max: {np.max(segmento_correlazione)}")
                        ax_riferimento = ax_confronto.twinx()
                        ax_confronto.plot(indici_assoluti, segmento_correlazione, label="Correlazione", color='green')
                        picchi_visibili = [p for p in picchi32 if inizio_offset <= p < fine_offset]
                        if picchi_visibili:
                            ax_confronto.plot(picchi_visibili, correlazione32[picchi_visibili], "x", color='darkorange', label='Picchi', markersize=10)
                        bit0_pos = [pos for bit, pos in bits32 if bit == 0 and inizio_offset <= pos < fine_offset]
                        bit0_val = [correlazione32[pos] for pos in bit0_pos]
                        bit1_pos = [pos for bit, pos in bits32 if bit == 1 and inizio_offset <= pos < fine_offset]
                        bit1_val = [correlazione32[pos] for pos in bit1_pos]
                        if bit0_pos:
                            ax_confronto.plot(bit0_pos, bit0_val, "o", color='green', label='Bit 0', markersize=8)
                        if bit1_pos:
                            ax_confronto.plot(bit1_pos, bit1_val, "o", color='red', label='Bit 1', markersize=8)
                        ax_riferimento.plot(indici_assoluti, riferimento[:len(indici_assoluti)], label="Segnale di riferimento", color='orange', alpha=0.7)
                        ax_confronto.set_ylabel("Correlazione", color='green')
                        ax_riferimento.set_ylabel("Ampiezza Riferimento", color='orange')
                        if segmento_correlazione.size > 0 and np.any(segmento_correlazione):
                            corr_min, corr_max = np.min(segmento_correlazione), np.max(segmento_correlazione)
                            ylim_corr = (corr_min - 0.1 * (corr_max - corr_min), corr_max + 0.1 * (corr_max - corr_min))
                            ax_confronto.set_ylim(ylim_corr)
                        else:
                            ylim_corr = (-1, 1)
                            ax_confronto.set_ylim(ylim_corr)
                        ax_riferimento.set_ylim(-1.5, 1.5)
                        lines1, labels1 = ax_confronto.get_legend_handles_labels()
                        lines2, labels2 = ax_riferimento.get_legend_handles_labels()
                        ax_confronto.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
                        ax_confronto.set_title(f"Correlazione ESP32 (inizio: {inizio_offset})")
                    else:
                        ax_confronto.text(0.5, 0.5, "Dati ESP32 non disponibili", ha='center', va='center')
                        ax_confronto.set_title(f"Correlazione ESP32 (inizio: {inizio_offset})")
                        ax_confronto.set_ylabel("Correlazione")

                ax_confronto.set_xlabel("Campioni")
                # Ripristina o aggiorna lo zoom
                ax_confronto.set_xlim(xlim)
                print(f"Debug: Limiti x impostati: {xlim}")
                canvas.draw()

            def sposta_sinistra():
                nonlocal offset, previous_offset
                offset += 1
                previous_offset = offset
                aggiorna_grafico(offset)

            def sposta_destra():
                nonlocal offset, previous_offset
                offset -= 1
                previous_offset = offset
                aggiorna_grafico(offset)

            def seleziona_picco_precedente():
                nonlocal current_peak_idx, idx_max, offset, previous_offset, previous_idx_max
                if current_peak_idx > 0:
                    current_peak_idx -= 1
                    idx_max = risultati[current_peak_idx][1]
                    offset = 0
                    previous_offset = 0
                    previous_idx_max = idx_max
                    print(f"Debug: Picco precedente, idx_max: {idx_max}")
                    aggiorna_grafico(offset)

            def seleziona_picco_successivo():
                nonlocal current_peak_idx, idx_max, offset, previous_offset, previous_idx_max
                if current_peak_idx < len(risultati) - 1:
                    current_peak_idx += 1
                    idx_max = risultati[current_peak_idx][1]
                    offset = 0
                    previous_offset = 0
                    previous_idx_max = idx_max
                    print(f"Debug: Picco successivo, idx_max: {idx_max}")
                    aggiorna_grafico(offset)

            def imposta_inizio(valore):
                nonlocal offset, idx_max, previous_offset, previous_idx_max
                try:
                    nuovo_inizio = int(valore)
                    if 0 <= nuovo_inizio <= len(segnale) - lunghezza_riferimento:
                        offset = nuovo_inizio - (idx_max - lunghezza_riferimento)
                        previous_offset = offset
                        previous_idx_max = idx_max
                        print(f"Debug: Imposta inizio, nuovo_inizio: {nuovo_inizio}, offset: {offset}")
                        aggiorna_grafico(offset)
                except ValueError:
                    pass

            if _confronto_window is None or not _confronto_window.winfo_exists():
                _confronto_window = tk.Toplevel()
                _confronto_window.title("Confronto Segnale e Correlazione")
                frame = tk.Frame(_confronto_window)
                frame.pack(fill=tk.BOTH, expand=True)
                fig_confronto, ax_confronto = plt.subplots(figsize=(10, 6))
                canvas = FigureCanvasTkAgg(fig_confronto, master=frame)
                canvas.draw()
                canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
                toolbar = NavigationToolbar2Tk(canvas, frame)
                toolbar.update()
                canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
                radio_frame = tk.Frame(_confronto_window)
                radio_frame.pack(side=tk.TOP, fill=tk.X)
                mostra_var = tk.IntVar(value=0)
                tk.Radiobutton(radio_frame, text="Segnale", variable=mostra_var, value=0, command=lambda: aggiorna_grafico(offset)).pack(side=tk.LEFT, padx=5)
                tk.Radiobutton(radio_frame, text="Correlazione ESP32", variable=mostra_var, value=1, command=lambda: aggiorna_grafico(offset)).pack(side=tk.LEFT, padx=5)
                button_frame = tk.Frame(_confronto_window)
                button_frame.pack(side=tk.BOTTOM, fill=tk.X)
                tk.Button(button_frame, text="Sposta Sinistra", command=sposta_sinistra).pack(side=tk.LEFT, padx=5)
                tk.Button(button_frame, text="Sposta Destra", command=sposta_destra).pack(side=tk.LEFT, padx=5)
                tk.Button(button_frame, text="Picco Precedente", command=seleziona_picco_precedente).pack(side=tk.LEFT, padx=5)
                tk.Button(button_frame, text="Picco Successivo", command=seleziona_picco_successivo).pack(side=tk.LEFT, padx=5)
                tk.Label(button_frame, text="Campione Iniziale:").pack(side=tk.LEFT, padx=5)
                entry_inizio = tk.Entry(button_frame, width=10)
                entry_inizio.pack(side=tk.LEFT, padx=5)
                tk.Button(button_frame, text="Imposta Inizio", command=lambda: imposta_inizio(entry_inizio.get())).pack(side=tk.LEFT, padx=5)
                def _close_window():
                    global _confronto_window
                    _confronto_window.destroy()
                    _confronto_window = None
                _confronto_window.protocol("WM_DELETE_WINDOW", _close_window)
            else:
                for widget in _confronto_window.winfo_children():
                    if isinstance(widget, tk.Frame):
                        for child in widget.winfo_children():
                            if isinstance(child, tk.Canvas):
                                canvas = child.master
                                fig_confronto = canvas.figure
                                ax_confronto = fig_confronto.axes[0]
                                break

            aggiorna_grafico(offset)

        risultato_text.delete(1.0, tk.END)
        if risultati:
            max_conf = abs(risultati[0][0])
            risultato_text.insert(tk.END, f"Confidenza massima: {max_conf:.3f}\n")
            for conf, idx, bit in risultati:
                risultato_text.insert(tk.END, f"Confidenza {conf:.3f} al bit {bit} ({idx})\n")
        else:
            risultato_text.insert(tk.END, "Nessuna corrispondenza trovata\n")

        ax2 = ax1.twinx()
        ax2.clear()
        indici = np.arange(min(len(correlazione), 10000))
        ax2.plot(indici, correlazione[:10000], 'r-', label='Correlazione', alpha=0.5)
        ax2.set_ylabel('Correlazione')
        ax2.set_xlim(0, 10000)
        ax2.legend()
        ax1.figure.canvas.draw()
        status_label.config(text="Stato: Correlazione completata")
    except Exception as e:
        print(f"Errore in correlazione_con_sequenza_nota: {e}")
        status_label.config(text=f"Erre: {e}")
        risultato_text.delete(1.0, tk.END)
        risultato_text.insert(tk.END, f"Errore: {e}\n")