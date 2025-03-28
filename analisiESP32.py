import tkinter as tk
import numpy as np
import matplotlib.pyplot as plt
import struct

# Nuova funzione che combina media mobile e correlazione
def media_correlazione_32(segnale, larghezza_finestra=8, lunghezza_correlazione=32):
    """
    Calcola la media mobile e la correlazione scorrevole su interi a 32 bit in un unico loop.
    
    Parametri:
    - segnale: array del segnale di ingresso
    - larghezza_finestra: numero di campioni per la media mobile (default: 8)
    - lunghezza_correlazione: lunghezza della finestra di correlazione (default: 32)
    
    Ritorna:
    - segnale_filtrato32: array della media mobile
    - correlazione32: array della correlazione scorrevole
    """
    N = len(segnale)
    segnale_32 = np.array(segnale, dtype=np.int32)
    segnale_filtrato32 = np.zeros(N, dtype=np.int32)
    correlazione32 = np.zeros(N, dtype=np.int32)
    
    # Azzeramento dei primi valori
    for i in range(28):  # I primi 28 valori di segnale_filtrato32 sono 0
        segnale_filtrato32[i] = 0
    for i in range(16):  # I primi 16 valori di correlazione32 sono 0
        correlazione32[i] = 0
    
    # Calcolo iniziale per i=32
    i = 32
    if i < N:
        # Media mobile iniziale (finestra da i-4 a i+3)
        if i + 3 < N:
            somma_media = np.sum(segnale_32[i-4:i+4], dtype=np.int32)
            segnale_filtrato32[i] = somma_media // larghezza_finestra
        else:
            segnale_filtrato32[i] = 0  # Non abbastanza dati
    
    # Correlazione iniziale per i=32, centrata su i-16=16
    if i >= lunghezza_correlazione:
        correlazione32[16] = 0
        for j in range(16):
            correlazione32[16] += segnale_filtrato32[j]
        for j in range(16, 32):
            correlazione32[16] -= segnale_filtrato32[j]
    
    # Loop principale ottimizzato
    for i in range(33, N-4):
        segnale_filtrato32[i] = segnale_filtrato32[i-1] - segnale_32[i-4] + segnale_32[i+3]
        correlazione32[i-16] = correlazione32[i-17] - segnale_filtrato32[i-32] + 2 * segnale_filtrato32[i-16] - segnale_filtrato32[i]
    
    # Azzeramento dei primi 64 valori di correlazione32 DOPO il calcolo
    correlazione32[:64] = 0
    
    return segnale_filtrato32, correlazione32

# Funzione principale per l'analisi
def analizza_con_buffer_scorrevole(percorso_file, status_label):
    """
    Analizza il file con un approccio a buffer scorrevole, usando la correlazione.
    """
    # Parametri di campionamento
    periodo_campionamento = 1 / 134.2e3 * 1e6  # in microsecondi
    durata_bit = 1 / (134.2e3 / 32) * 1e6      # in microsecondi
    campioni_per_bit = int(durata_bit / periodo_campionamento)

    # Lettura del file binario
    with open(percorso_file, "rb") as f:
        dati = f.read()
    segnale_32 = np.array(struct.unpack("<" + "h" * (len(dati) // 2), dati), dtype=np.int32)

    # Calcolo della media mobile e della correlazione
    segnale_filtrato32, correlazione32 = media_correlazione_32(segnale_32)

    # Aggiornamento dello stato
    status_label.config(text="Stato: Analisi ESP32 - Media e correlazione completate")

    # Visualizzazione del segnale e della correlazione
    visualizza_analisi_esp32(segnale_32, correlazione32, campioni_per_bit)

    return []  # Lista vuota per ora (puoi aggiungere decodifica dei bit se necessario)

# Funzione per la visualizzazione
def visualizza_analisi_esp32(segnale_32, correlazione32, campioni_per_bit):
    """
    Crea una finestra con due grafici: segnale di ingresso e correlazione.
    """
    # Creazione della finestra Tkinter
    window32 = tk.Tk()
    window32.title("Analisi ESP32")

    # Creazione della figura Matplotlib
    fig32, (ax1_32, ax2_32) = plt.subplots(2, 1, figsize=(12, 9))
    plt.tight_layout()

    # Grafico 1: Segnale di ingresso
    ax1_32.plot(segnale_32, label="Segnale (32-bit)", color='blue')
    for i in range(0, len(segnale_32), campioni_per_bit):
        ax1_32.axvline(i, color='black', linestyle='-', linewidth=0.8)
        ax1_32.axvline(i + campioni_per_bit // 2, color='gray', linestyle='--', linewidth=0.5)
    ax1_32.set_title('Segnale di Ingresso (ESP32)')
    ax1_32.legend()

    # Grafico 2: Correlazione
    ax2_32.plot(correlazione32, label='Correlazione (32-bit)', color='green')
    for i in range(0, len(correlazione32), campioni_per_bit):
        ax2_32.axvline(i, color='black', linestyle='-', linewidth=0.8)
        ax2_32.axvline(i + campioni_per_bit // 2, color='gray', linestyle='--', linewidth=0.5)
    ax2_32.set_title('Correlazione (ESP32)')
    ax2_32.legend()

    # Sincronizzazione degli assi
    def sincronizza_assi_32(event):
        if event.inaxes == ax1_32:
            ax2_32.set_xlim(ax1_32.get_xlim())
        elif event.inaxes == ax2_32:
            ax1_32.set_xlim(ax2_32.get_xlim())
        fig32.canvas.draw_idle()

    fig32.canvas.mpl_connect('motion_notify_event', sincronizza_assi_32)

    # Mostra i grafici
    plt.show(block=False)
    window32.mainloop()