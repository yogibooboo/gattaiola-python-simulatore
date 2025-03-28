import tkinter as tk
import numpy as np
import matplotlib.pyplot as plt
import struct

# Funzione per la media mobile a 32 bit con finestra fissa di 8 campioni (metodo scorrevole)
def media_mobile_32(segnale, larghezza_finestra=8):
    """Calcola la somma mobile su una finestra fissa di 8 campioni usando interi a 32 bit."""
    segnale_32 = np.array(segnale, dtype=np.int32)  # Converti in interi a 32 bit
    risultato = np.zeros(len(segnale) - larghezza_finestra + 1, dtype=np.int32)
    
    # Inizializza la somma per la prima finestra
    somma = np.sum(segnale_32[:larghezza_finestra], dtype=np.int32)
    risultato[0] = somma
    
    # Calcolo scorrevole per le finestre successive
    for i in range(1, len(risultato)):
        somma = somma - segnale_32[i - 1] + segnale_32[i + larghezza_finestra - 1]
        risultato[i] = somma
    
    return risultato

# Funzione principale per l'analisi ESP32
def analizza_con_buffer_scorrevole(percorso_file, status_label):
    """Analizza il file con un approccio a buffer scorrevole adatto per ESP32."""
    # Parametri di campionamento
    periodo_campionamento = 1 / 134.2e3 * 1e6
    durata_bit = 1 / (134.2e3 / 32) * 1e6
    campioni_per_bit = int(durata_bit / periodo_campionamento)

    # Lettura del file
    with open(percorso_file, "rb") as f:
        dati = f.read()
    segnale_32 = np.array(struct.unpack("<" + "h" * (len(dati) // 2), dati), dtype=np.int32)

    # Calcolo della media mobile (solo somma, senza divisione)
    segnale_filtrato32 = media_mobile_32(segnale_32)

    # Aggiornamento dello stato
    status_label.config(text="Stato: Analisi ESP32 - Media mobile completata")

    # Visualizzazione nella nuova finestra
    visualizza_analisi_esp32(segnale_32, segnale_filtrato32, campioni_per_bit)

    return []  # Per ora restituiamo una lista vuota di bit

# Funzione per creare e gestire la finestra di visualizzazione ESP32
def visualizza_analisi_esp32(segnale_32, segnale_filtrato32, campioni_per_bit):
    """Crea una nuova finestra con due grafici per l'analisi ESP32."""
    # Creazione della finestra
    window32 = tk.Tk()
    window32.title("Analisi ESP32")

    # Buffer a 32 bit (inizializzati vuoti per i passi successivi)
    correlazione32 = np.array([], dtype=np.int32)  # Da riempire successivamente
    picchi32 = np.array([], dtype=np.int32)        # Da riempire successivamente

    # Creazione della figura Matplotlib
    fig32, (ax1_32, ax2_32) = plt.subplots(2, 1, figsize=(12, 9))
    plt.tight_layout()

    # Grafico 1: Segnale di ingresso (solo segnale_32)
    ax1_32.plot(segnale_32, label="Segnale (32-bit)", color='blue')
    for i in range(0, len(segnale_32), campioni_per_bit):
        ax1_32.axvline(i, color='black', linestyle='-', linewidth=0.8)
        ax1_32.axvline(i + campioni_per_bit // 2, color='gray', linestyle='--', linewidth=0.5)
    ax1_32.set_title('Segnale di Ingresso (ESP32)')
    ax1_32.legend()

    # Grafico 2: Segnale filtrato (segnale_filtrato32)
    ax2_32.plot(segnale_filtrato32, label='Segnale Filtrato - Somma 8 (32-bit)', color='orange')
    for i in range(0, len(segnale_filtrato32), campioni_per_bit):
        ax2_32.axvline(i, color='black', linestyle='-', linewidth=0.8)
        ax2_32.axvline(i + campioni_per_bit // 2, color='gray', linestyle='--', linewidth=0.5)
    ax2_32.set_title('Segnale Filtrato (ESP32)')
    ax2_32.legend()

    # Funzione per sincronizzare gli assi
    def sincronizza_assi_32(event):
        if event.inaxes == ax1_32:
            ax2_32.set_xlim(ax1_32.get_xlim())
        elif event.inaxes == ax2_32:
            ax1_32.set_xlim(ax2_32.get_xlim())
        fig32.canvas.draw_idle()

    # Connessione della callback per la sincronizzazione
    fig32.canvas.mpl_connect('motion_notify_event', sincronizza_assi_32)

    # Mostra la finestra
    plt.show(block=False)
    window32.mainloop()

# Esempio di utilizzo standalone (per debug)
if __name__ == "__main__":
    class DummyLabel:
        def config(self, text):
            print(text)

    percorso = "percorso_del_tuo_file.bin"  # Sostituisci con un percorso reale per test
    analizza_con_buffer_scorrevole(percorso, DummyLabel())