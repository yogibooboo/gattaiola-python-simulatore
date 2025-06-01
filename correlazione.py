import numpy as np
from scipy.signal import find_peaks
import struct
import matplotlib.pyplot as plt
import tkinter as tk

# Sequenza nota: 10 byte esadecimale (8 dati + 2 CRC)
BYTES_NOTI = [0x54, 0xDD, 0x25, 0x3C, 0x3D, 0xE1, 0x01, 0x80, 0x1C, 0xC9]

def genera_sequenza_bit(bytes_noti):
    """Genera la sequenza di 101 bit da 10 byte esadecimale."""
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
        print(f"Debug: Errore in genera_sequenza_bit: {e}")
        raise

def genera_segnale_riferimento(sequenza_bit):
    """Genera il segnale di riferimento di 1616 campioni dai 101 bit."""
    print("Debug: Generazione segnale di riferimento...")
    try:
        campioni_per_bit = 16
        segnale = np.zeros(len(sequenza_bit) * campioni_per_bit)
        polarita = 1
        for i, bit in enumerate(sequenza_bit):
            inizio = i * campioni_per_bit
            polarita = -polarita
            if bit == 1:
                segnale[inizio:inizio + campioni_per_bit] = polarita
            else:
                segnale[inizio:inizio + 8] = polarita
                segnale[inizio + 8:inizio + campioni_per_bit] = -polarita
        segnale = segnale / np.linalg.norm(segnale) if np.linalg.norm(segnale) != 0 else segnale
        print(f"Debug: Lunghezza segnale riferimento: {len(segnale)}")
        print(f"Debug: Primi 50 campioni riferimento: {segnale[:50]}")
        return segnale
    except Exception as e:
        print(f"Debug: Errore in genera_segnale_riferimento: {e}")
        raise

def correlazione_con_sequenza_nota(percorso_file, bytes_noti, status_label, ax1, risultato_text, segnale_filtrato=None):
    """Calcola la correlazione con la sequenza nota e aggiorna il grafico e la GUI."""
    print("Debug: Inizio funzione correlazione...")
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

        # Rimuovi sottocampionamento per mantenere risoluzione
        # segnale = segnale[::2]
        print(f"Debug: Lunghezza segnale: {len(segnale)}")
        segnale = segnale - np.mean(segnale)
        segnale = segnale / np.linalg.norm(segnale) if np.linalg.norm(segnale) != 0 else segnale

        print("Debug: Generazione sequenza bit e riferimento...")
        bits = genera_sequenza_bit(bytes_noti)
        riferimento = genera_segnale_riferimento(bits)

        print("Debug: Calcolo correlazione...")
        correlazione = np.correlate(segnale, riferimento, mode='full')
        norm = np.sqrt(np.sum(segnale**2) * np.sum(riferimento**2))
        correlazione = correlazione / norm if norm != 0 else correlazione
        print(f"Debug: Lunghezza correlazione: {len(correlazione)}, max: {np.max(np.abs(correlazione)):.3f}")

        soglia = 0.3
        print(f"Debug: Ricerca picchi con soglia {soglia}...")
        picchi_pos, props_pos = find_peaks(correlazione, height=soglia)
        picchi_neg, props_neg = find_peaks(-correlazione, height=soglia)
        print(f"Debug: Picchi positivi: {len(picchi_pos)}, Picchi negativi: {len(picchi_neg)}")

        risultati = []
        for idx in picchi_pos:
            risultati.append((correlazione[idx], idx // 16))
        for idx in picchi_neg:
            risultati.append((-correlazione[idx], idx // 16))
        risultati.sort(key=lambda x: abs(x[0]), reverse=True)
        print(f"Debug: Totale picchi trovati: {len(risultati)}")

        print("Debug: Aggiornamento risultato_text...")
        risultato_text.delete(1.0, tk.END)
        if risultati:
            max_conf = abs(risultati[0][0])
            risultato_text.insert(tk.END, f"Confidenza massima: {max_conf:.3f}\n")
            risultato_text.insert(tk.END, "Corrispondenze trovate:\n")
            for conf, bit in risultati:
                risultato_text.insert(tk.END, f"Confidenza {conf:.3f} al bit {bit}\n")
        else:
            risultato_text.insert(tk.END, f"Nessuna corrispondenza sopra la soglia {soglia}\n")
            risultato_text.insert(tk.END, f"Valore massimo correlazione: {np.max(np.abs(correlazione)):.3f}\n")

        print("Debug: Aggiornamento grafico...")
        ax2 = ax1.twinx()
        ax2.plot(correlazione, 'b-', label='Correlazione', alpha=0.5)
        for idx in picchi_pos:
            ax2.plot(idx, correlazione[idx], 'rx', label='Picco positivo' if idx == picchi_pos[0] else "", markersize=10)
        for idx in picchi_neg:
            ax2.plot(idx, -correlazione[idx], 'bx', label='Picco negativo' if idx == picchi_neg[0] else "", markersize=10)
        ax2.axhline(soglia, color='g', linestyle='--', label='Soglia positiva')
        ax2.axhline(-soglia, color='g', linestyle='--', label='Soglia negativa')
        ax2.set_ylabel('Correlazione')
        ax2.legend(loc='upper right')
        ax2.set_ylim(-1, 1)  # Normalizza la scala
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