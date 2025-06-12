import numpy as np

def create_fdx_b_signal():
    # Parametri
    SAMPLES_PER_BIT = 32  # 32 valori per bit
    SAMPLES_PER_HALF = 16  # 16 valori per metà bit
    TOTAL_SAMPLES = 10000  # Totale campioni nel file
    CENTER_VALUE = 2048   # Valore centrale ADC
    AMPLITUDE = 200       # Ampiezza oscillazione
    BIT_SEQUENCE = [
        0,0,0,0,0,0,0,0,0,0,1,0,0,1,0,1,0,1,0,1,1,0,1,1,1,0,1,1,1,1,0,1,
        0,0,1,0,0,1,0,0,1,1,1,1,0,0,1,1,0,1,1,1,1,0,0,1,1,0,0,0,0,1,1,1,
        1,1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1,1,0,0,1,1,1,0,0,0,1,1,0,0,1,
        0,0,1,1,1,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,0,1,0,1,0,1,0,1,1
    ]  # Sequenza di 128 bit

    # Calcola quante volte la sequenza si ripete e i campioni rimanenti
    total_bits = TOTAL_SAMPLES // SAMPLES_PER_BIT
    samples = np.zeros(TOTAL_SAMPLES, dtype=np.uint16)

    last_half_value = -AMPLITUDE  # Inizializzazione arbitraria per il primo bit

    sample_idx = 0
    while sample_idx < TOTAL_SAMPLES:
        for bit in BIT_SEQUENCE:
            if sample_idx >= TOTAL_SAMPLES:
                break
                
            # Prima metà: opposta all'ultima metà del bit precedente
            first_half_value = -last_half_value
            
            # Seconda metà: dipende dal bit
            if bit == 0:
                second_half_value = -first_half_value  # Cambia segno se bit è 0
            else:
                second_half_value = first_half_value   # Stesso segno se bit è 1
                
            # Riempie i campioni per la prima metà
            for i in range(min(SAMPLES_PER_HALF, TOTAL_SAMPLES - sample_idx)):
                samples[sample_idx + i] = CENTER_VALUE + first_half_value
                
            sample_idx += SAMPLES_PER_HALF
            
            # Riempie i campioni per la seconda metà
            for i in range(min(SAMPLES_PER_HALF, TOTAL_SAMPLES - sample_idx)):
                samples[sample_idx + i] = CENTER_VALUE + second_half_value
                
            sample_idx += SAMPLES_PER_HALF
            
            # Aggiorna l'ultima metà per il prossimo bit
            last_half_value = second_half_value

    # Scrittura su file binario in formato little-endian
    with open('fdx_b_signal.bin', 'wb') as f:
        samples.tofile(f)

    print("File 'fdx_b_signal.bin' creato con successo!")

# Esegui la funzione
create_fdx_b_signal()