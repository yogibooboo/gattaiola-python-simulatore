import tkinter as tk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import struct

# Settaggio univoco per la finestra di correlazione
FINESTRA_ESTESA = False  # True per finestra estesa (64 campioni), False per standard (32 campioni)

# Variabile globale per memorizzare l'ultimo offset
ULTIMO_OFFSET = None  # Offset medio non arrotondato dell'ultima sequenza di sync

# Variabili globali per i dati di correlazione
_correlazione32 = None
_picchi32 = None
_bits32 = None
_ax1_32 = None

def media_correlazione_32(segnale, larghezza_finestra=8, lunghezza_correlazione=32, log_callback=None):
    print("Debug: Inizio media_correlazione_32...")
    print(f"Debug: Finestra di correlazione: {'estesa (64 campioni)' if FINESTRA_ESTESA else 'standard (32 campioni)'}")
    global ULTIMO_OFFSET, _correlazione32, _picchi32, _bits32
    N = len(segnale)
    segnale_32 = np.array(segnale, dtype=np.int32)
    segnale_filtrato32 = np.zeros(N, dtype=np.int32)
    correlazione32 = np.zeros(N, dtype=np.int32)
    picchi32 = []
    distanze = []
    bits32 = []
    bytes32 = []
    soglia_mezzo_bit = 24
    stato_decodifica = 0
    contatore_zeri = 0
    contatore_bytes = 0
    contatore_bits = 0
    stato_decobytes = 0
    crc = 0
    polynomial = 0x1021
    total_bits = 0  # Contatore bit totali
    last_sync_bit = 0  # Ultimo bit di sync

    def log_message(message):
        if log_callback:
            log_callback(message)
        print(message)

    # Inizializzazione array
    for i in range(28):
        segnale_filtrato32[i] = 0
    for i in range(16):
        correlazione32[i] = 0

    i = 32
    if i < N and i + 3 < N:
        somma_media = np.sum(segnale_32[i-4:i+4], dtype=np.int32)
        segnale_filtrato32[i] = somma_media // larghezza_finestra

    # Calcolo della correlazione
    if FINESTRA_ESTESA:
        lunghezza_correlazione = 64
        if i >= lunghezza_correlazione:
            correlazione32[16] = 0
            for j in range(-16, 0):  # -16
                correlazione32[16] -= segnale_filtrato32[j]
            for j in range(0, 16):  # +16
                correlazione32[16] += segnale_filtrato32[j]
            for j in range(16, 32):  # -16
                correlazione32[16] -= segnale_filtrato32[j]
            for j in range(32, 48):  # +16
                correlazione32[16] += segnale_filtrato32[j]
    else:
        lunghezza_correlazione = 32
        if i >= lunghezza_correlazione:
            correlazione32[16] = 0
            for j in range(16):  # +16
                correlazione32[16] += segnale_filtrato32[j]
            for j in range(16, 32):  # -16
                correlazione32[16] -= segnale_filtrato32[j]

    max_i = max_i8 = min_i = min_i8 = 0
    stato = 1
    if N > 24:
        max_i = min_i = correlazione32[16]
        max_i8 = min_i8 = correlazione32[8]

    for i in range(33, N-4):
        segnale_filtrato32[i] = segnale_filtrato32[i-1] - (segnale_32[i-4] // larghezza_finestra) + (segnale_32[i+3] // larghezza_finestra)
        if FINESTRA_ESTESA:
            correlazione32[i-16] = correlazione32[i-17] - segnale_filtrato32[i-48] + segnale_filtrato32[i-32] - segnale_filtrato32[i-16] + segnale_filtrato32[i]
        else:
            correlazione32[i-16] = correlazione32[i-17] - segnale_filtrato32[i-32] + 2 * segnale_filtrato32[i-16] - segnale_filtrato32[i]

        newbit = 2
        numbit = 0
        newpeak = False

        if stato == 1:
            max_i = max(correlazione32[i-16], max_i)
            max_i8 = max(correlazione32[i-24], max_i8)
            if max_i == max_i8:
                picchi32.append(i-24)
                stato = -1
                min_i = correlazione32[i-16]
                min_i8 = correlazione32[i-24]
                newpeak = True
        else:
            min_i = min(correlazione32[i-16], min_i)
            min_i8 = min(correlazione32[i-24], min_i8)
            if min_i == min_i8:
                picchi32.append(i-24)
                stato = 1
                max_i = correlazione32[i-16]
                max_i8 = correlazione32[i-24]
                newpeak = True

        if len(picchi32) > 1 and newpeak:
            nuova_distanza = picchi32[-1] - picchi32[-2]
            distanze.append(nuova_distanza)
            if stato_decodifica == 0:
                if nuova_distanza >= soglia_mezzo_bit:
                    bits32.append((1, i-24))
                    newbit = 1
                    numbit = 1
                else:
                    stato_decodifica = 1
            elif stato_decodifica ==1:    #2006   == 1: potrebbe essre 2 in caso di doppia correzione
                if True:   #2006 nuova_distanza < soglia_mezzo_bit:
                    # PRIMA PROVA: se la somma delle ultime due distanze è maggiore di 32+8 allora il primo era un 1 e il secondo è l'inizio di uno zero
                    if len(distanze) >= 2 and (nuova_distanza + distanze[-2]) >= 46:
                    
                        bits32.append((1, i-24))
                        newbit = 1
                        numbit = 1
                        stato_decodifica = 2 #2006 stato_decodifica = 2
                        #aggiusta
                    else:
                        bits32.append((0, i-24))
                        newbit = 0
                        numbit = 1
                        stato_decodifica = 0
                else:
                    bits32.append((1, i-24-nuova_distanza))
                    bits32.append((1, i-24))
                    newbit = 1
                    numbit = 2
                    stato_decodifica = 0
            elif stato_decodifica ==2:    #2006  potrebbe essre 2 in caso di doppia correzione
                bits32.append((0, i-24))
                newbit = 0
                numbit = 1
                stato_decodifica = 0
 

        while numbit > 0:
            total_bits += 1  # Incrementa bit totali
            if stato_decobytes == 0:
                if newbit == 0:
                    contatore_zeri += 1
                else:
                    if contatore_zeri == 10: #2806 contatore_zeri >= 10:
                        stato_decobytes = 1
                        contatore_bytes = 0
                        contatore_bits = 0
                        bytes32 = [0] * 10
                        sync_pos = i - 24
                        sync_bit = total_bits
                        last_sync_bit = sync_bit  # Salva ultimo sync
                        inizio_pos = sync_pos - 352
                        inizio_bit = sync_bit - 11
                        # Calcolo dell'offset medio per gli 8 bit a zero centrali
                        zero_positions = [pos for bit, pos in bits32[-10:]]  # Ultimi 10 bit a zero
                        offset_medio = sum(pos % 32 for pos in zero_positions[1:-1]) / 8
                        offset = round(offset_medio)
                        ULTIMO_OFFSET = offset_medio  # Salva l'offset non arrotondato
                        log_message(f"Sync at: {sync_pos} (bit: {sync_bit}), inizio: {inizio_pos} (bit: {inizio_bit}), offset: {offset}")
                    contatore_zeri = 0
            elif stato_decobytes == 1:
                if contatore_bits < 8:
                    bytes32[contatore_bytes] >>= 1
                    if newbit == 1:
                        bytes32[contatore_bytes] |= 0x80
                    contatore_bits += 1
                else:
                    if newbit == 1:
                        contatore_bytes += 1
                        contatore_bits = 0
                    if contatore_bytes >= 10:
                        hex_bytes = [f"{byte:02X}" for byte in bytes32]
                        log_message(f"Byte estratti: [{', '.join(hex_bytes)}]")
                        dati = bytes32[:-2]
                        crc_ricevuto = (bytes32[-1] << 8) | bytes32[-2]
                        crc = 0x0
                        for byte in dati:
                            b = byte
                            for j in range(8):
                                bit = ((b >> j) & 1) == 1
                                c15 = ((crc >> 15) & 1) == 1
                                crc <<= 1
                                if c15 ^ bit:
                                    crc ^= polynomial
                            crc &= 0xffff
                        crc_reversed = 0
                        for j in range(16):
                            if (crc >> j) & 1:
                                crc_reversed |= 1 << (15 - j)
                        if crc_ricevuto == crc_reversed:
                            log_message("CRC OK")
                            country_code = (bytes32[5] << 2) | (bytes32[4] >> 6)
                            device_code = (bytes32[4] & 0x3F) << 32 | \
                                          (bytes32[3] << 24) | \
                                          (bytes32[2] << 16) | \
                                          (bytes32[1] << 8) | bytes32[0]
                            log_message(f"Country Code: {country_code}")
                            log_message(f"Device Code: {device_code}")
                        else:
                            log_message(f"CRC: {crc_reversed:04X}")
                        contatore_zeri = 0
                        contatore_bytes = 0
                        stato_decobytes = 0
                    elif newbit != 1:
                        byte_count = (total_bits - last_sync_bit) // 9  # Calcola byte
                        hex_bytes_parziali = [f"{byte:02X}" for byte in bytes32[:contatore_bytes]]
                        log_message(f"Perso sync at: {i-24} (bit: {total_bits}, byte: {byte_count}, byte acquisiti: [{', '.join(hex_bytes_parziali)}])")
                        contatore_zeri = 0
                        contatore_bits = 0
                        stato_decobytes = 0
            numbit -= 1  # Decrementa correttamente

    if not bytes32:
        log_message("Nessuna sequenza di byte valida trovata")
    
    # Salva i dati globalmente
    _correlazione32 = correlazione32
    _picchi32 = picchi32
    _bits32 = bits32

    print(f"Debug: Segnale filtrato restituito, lunghezza: {len(segnale_filtrato32)}")
    return segnale_filtrato32, correlazione32, picchi32, distanze, bits32, bytes32

def analizza_con_buffer_scorrevole(percorso_file, status_label, log_callback=None):
    print("Debug: Inizio analizza_con_buffer_scorrevole...")
    periodo_campionamento = 1 / 134.2e3 * 1e6
    durata_bit = 1 / (134.2e3 / 32) * 1e6
    campioni_per_bit = int(durata_bit / periodo_campionamento)
    with open(percorso_file, "rb") as f:
        dati = f.read()
    segnale = np.array(struct.unpack("<" + "h" * (len(dati) // 2), dati))
    print(f"Debug: Segnale letto, lunghezza: {len(segnale)}")
    segnale_filtrato32, correlazione32, picchi32, distanze32, bits32, bytes32 = media_correlazione_32(
        segnale, log_callback=log_callback)
    visualizza_analisi_esp32(segnale, correlazione32, picchi32, distanze32, bits32, bytes32, campioni_per_bit, segnale_filtrato32)
    print(f"Debug: Segnale filtrato restituito, lunghezza: {len(segnale_filtrato32)}")
    status_label.config(text="Stato: Analisi ESP32 - Media, correlazione e decodifica completati")
    return segnale_filtrato32

def visualizza_analisi_esp32(segnale, correlazione32, picchi32, distanze32, bits32, bytes32, campioni_per_bit, segnale_filtrato32):
    global _ax1_32
    print("Debug: Inizio visualizza_analisi_esp32...")
    window32 = tk.Toplevel()
    window32.title("Analisi ESP32")

    frame = tk.Frame(window32)
    frame.pack(fill=tk.BOTH, expand=True)

    # Variabile per i radiobutton
    mostra_segnale_var = tk.IntVar(value=0)  # 0 = Grezzo, 1 = Filtrato, 2 = Entrambi

    # Funzione per aggiornare il grafico
    def aggiorna_grafico_segnale():
        # Salva i limiti attuali degli assi per mantenere lo zoom
        xlim = ax1_32.get_xlim()
        ylim = ax1_32.get_ylim()
        
        ax1_32.clear()
        scelta = mostra_segnale_var.get()
        
        # Plotta in base alla selezione
        if scelta == 0:  # Grezzo
            ax1_32.plot(segnale, label="Segnale Grezzo", color='blue', alpha=0.8)
        elif scelta == 1:  # Filtrato
            ax1_32.plot(segnale_filtrato32, label="Segnale Filtrato", color='green', alpha=0.8)
        elif scelta == 2:  # Entrambi
            ax1_32.plot(segnale, label="Segnale Grezzo", color='blue', alpha=0.6)
            ax1_32.plot(segnale_filtrato32, label="Segnale Filtrato", color='green', alpha=0.6)

        # Aggiungi linee di riferimento
        for i in range(0, len(segnale), campioni_per_bit):
            ax1_32.axvline(i, color='black', linestyle='-', linewidth=0.8)
            ax1_32.axvline(i + campioni_per_bit // 2, color='gray', linestyle='--', linewidth=0.5)
        
        ax1_32.set_title('Segnale di Ingresso')
        ax1_32.set_xlabel("Campioni", loc='left')  # Etichetta a sinistra
        ax1_32.set_ylabel("Ampiezza")
        ax1_32.legend()
        
        # Ripristina i limiti degli assi
        ax1_32.set_xlim(xlim)
        ax1_32.set_ylim(ylim)
        
        fig32.canvas.draw()

    fig32, (ax1_32, ax2_32) = plt.subplots(2, 1, figsize=(10, 6))
    plt.tight_layout(pad=2.0)  # Aumenta il padding per evitare sovrapposizioni

    # Aggiungi radiobutton direttamente sopra il grafico
    canvas = FigureCanvasTkAgg(fig32, master=frame)
    canvas.draw()
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    # Frame per i radiobutton
    radio_frame = tk.Frame(frame)
    radio_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)
    tk.Label(radio_frame, text="Segnale di Ingresso", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
    tk.Radiobutton(radio_frame, text="Grezzo", variable=mostra_segnale_var, value=0, command=aggiorna_grafico_segnale).pack(side=tk.LEFT, padx=5)
    tk.Radiobutton(radio_frame, text="Filtrato", variable=mostra_segnale_var, value=1, command=aggiorna_grafico_segnale).pack(side=tk.LEFT, padx=5)
    tk.Radiobutton(radio_frame, text="Entrambi", variable=mostra_segnale_var, value=2, command=aggiorna_grafico_segnale).pack(side=tk.LEFT, padx=5)

    # Plotta il segnale iniziale (default: grezzo)
    ax1_32.plot(segnale, label="Segnale Grezzo", color='blue', alpha=0.8)
    for i in range(0, len(segnale), campioni_per_bit):
        ax1_32.axvline(i, color='black', linestyle='-', linewidth=0.8)
        ax1_32.axvline(i + campioni_per_bit // 2, color='gray', linestyle='--', linewidth=0.5)
    ax1_32.set_title('Segnale di Ingresso')
    ax1_32.set_xlabel("Campioni", loc='left')  # Etichetta a sinistra
    ax1_32.set_ylabel("Ampiezza")
    ax1_32.legend()

    ax2_32.plot(correlazione32, label='Correlazione', color='green')
    ax2_32.plot(picchi32, correlazione32[picchi32], "x", color='darkorange', label='Picchi', markersize=10, markeredgewidth=2)
    bit0_pos = [pos for bit, pos in bits32 if bit == 0]
    bit0_val = [correlazione32[pos] for pos in bit0_pos]
    bit1_pos = [pos for bit, pos in bits32 if bit == 1]
    bit1_val = [correlazione32[pos] for pos in bit1_pos]
    if bit0_pos:
        ax2_32.plot(bit0_pos, bit0_val, "o", color='green', label='Bit 0', markersize=8, markeredgewidth=1.5)
    if bit1_pos:
        ax2_32.plot(bit1_pos, bit1_val, "o", color='red', label='Bit 1', markersize=8, markeredgewidth=1)
    for i in range(0, len(correlazione32), campioni_per_bit):
        ax2_32.axvline(i, color='black', linestyle='--', linewidth=0.8)
        ax2_32.axvline(i + campioni_per_bit // 2, color='gray', linestyle='--', linewidth=0.5)
    ax2_32.set_title('Correlazione con Bit')
    ax2_32.set_xlabel("Campioni", loc='left')  # Correzione della stringa
    ax2_32.set_ylabel("Correlazione")
    ax2_32.legend()

    def sincronizza_assi_32(event):
        if event.inaxes == ax1_32:
            ax2_32.set_xlim(ax1_32.get_xlim())
        elif event.inaxes == ax2_32:
            ax1_32.set_xlim(ax2_32.get_xlim())
        fig32.canvas.draw()

    fig32.canvas.mpl_connect('motion_notify_event', sincronizza_assi_32)

    toolbar = NavigationToolbar2Tk(canvas, frame)
    toolbar.update()
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    _ax1_32 = ax1_32
    print("Debug: Fine visualizza_analisi_esp32")

def get_ax1_32():
    return _ax1_32

def get_correlazione32():
    return _correlazione32

def get_picchi32():
    return _picchi32

def get_bits32():
    return _bits32