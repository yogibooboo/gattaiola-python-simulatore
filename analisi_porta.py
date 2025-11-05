import os
import glob
import struct
import numpy as np
import matplotlib
matplotlib.use('TkAgg')  # Forza backend TkAgg per compatibilità con tkinter
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, filedialog

def leggi_file_porta(percorso_file):
    """Legge un file porta_*.bin e restituisce i dati estratti."""
    print(f"Debug: Lettura file {percorso_file}")
    try:
        with open(percorso_file, "rb") as f:
            header = f.read(16)
            if len(header) != 16:
                print(f"Errore: Intestazione non valida in {percorso_file}")
                return None
            num_campioni, timestamp, magnitude = struct.unpack("<Idf", header)
            if num_campioni != 16384:
                print(f"Errore: num_campioni ({num_campioni}) non valido in {percorso_file}")
                return None
            buffer_data = f.read()
            if len(buffer_data) != 32768:
                print(f"Errore: Lunghezza dati ({len(buffer_data)}) non valida in {percorso_file}")
                return None
            buffer_array = np.frombuffer(buffer_data, dtype=np.uint16)
            infrared = buffer_array & 0x0001
            detect = (buffer_array >> 1) & 0x0001
            door_open = (buffer_array >> 2) & 0x0001
            newcode = (buffer_array >> 3) & 0x0001  # Estrazione del bit newcode
            raw_angle = (buffer_array >> 4) & 0x0FFF
            angles = (raw_angle / 4095) * 360
            print(f"Debug: File {percorso_file} letto con successo")
            return {
                "timestamp": timestamp,
                "magnitude": magnitude,
                "infrared": infrared,
                "detect": detect,
                "door_open": door_open,
                "newcode": newcode,
                "angles": angles
            }
    except Exception as e:
        print(f"Errore nella lettura di {percorso_file}: {e}")
        return None

def calcola_timestamp_campioni(timestamp_ultimo, num_campioni):
    """Genera array di timestamp per ogni campione."""
    print(f"Debug: Calcolo timestamp per {num_campioni} campioni")
    ultimo = datetime.fromtimestamp(timestamp_ultimo)
    primo = ultimo - timedelta(seconds=(num_campioni - 1) * 0.1)
    return np.array([primo + timedelta(seconds=i * 0.1) for i in range(num_campioni)])

def riempi_gap(ultimo_campione, gap_secondi):
    """Crea campioni per riempire il gap temporale ripetendo l'ultimo campione."""
    num_campioni_gap = int(round(gap_secondi / 0.1))
    if num_campioni_gap <= 0:
        print(f"Debug: Nessun gap da riempire ({gap_secondi} secondi)")
        return None
    print(f"Debug: Riempimento gap di {num_campioni_gap} campioni")
    return {
        "infrared": np.full(num_campioni_gap, ultimo_campione["infrared"], dtype=np.uint16),
        "detect": np.full(num_campioni_gap, ultimo_campione["detect"], dtype=np.uint16),
        "door_open": np.full(num_campioni_gap, ultimo_campione["door_open"], dtype=np.uint16),
        "newcode": np.full(num_campioni_gap, 0, dtype=np.uint16),  # Newcode a 0 nei gap
        "angles": np.full(num_campioni_gap, ultimo_campione["angles"], dtype=np.float32),
        "tempi": np.array([ultimo_campione["tempo"] + timedelta(seconds=(i + 1) * 0.1) 
                          for i in range(num_campioni_gap)])
    }

def analizza_passaggi(angles, infrared, detect, door_open, newcode, tempi, soglia_trigger, soglia_conferma, k):
    """Analizza il buffer per identificare i passaggi dei gatti."""
    print(f"Debug: Avvio analisi passaggi con soglie {soglia_trigger}/{soglia_conferma}, k={k}")
    ANGOLO_RIPOSO = 180.0
    log = []
    stato = "IDLE"
    timestamp_inizio = None
    indice_inizio = 0
    conteggio_senza_trigger = 0
    passaggio_confermato = False
    direzione = None
    trigger_porta_idx = -1
    passaggio_porta_idx = -1
    detect_idx = -1
    infrared_idx = -1
    ultimo_trigger_idx = 0
    fine_evento_idx = 0

    for i in range(len(angles)):
        angolo_deviazione = abs(angles[i] - ANGOLO_RIPOSO)
        trigger = (angolo_deviazione > soglia_trigger or infrared[i] == 1 or detect[i] == 1)

        if stato == "IDLE" and trigger:
            stato = "EVENTO_ATTIVO"
            timestamp_inizio = tempi[i]
            indice_inizio = i
            passaggio_confermato = False
            direzione = None
            conteggio_senza_trigger = 0
            trigger_porta_idx = i if angolo_deviazione > soglia_trigger else -1
            passaggio_porta_idx = -1
            detect_idx = i if detect[i] == 1 else -1
            infrared_idx = i if infrared[i] == 1 else -1
            ultimo_trigger_idx = i
            print(f"Debug: Evento iniziato a {timestamp_inizio}")

        elif stato == "EVENTO_ATTIVO":
            if trigger_porta_idx == -1 and angolo_deviazione > soglia_trigger:
                trigger_porta_idx = i
            if passaggio_porta_idx == -1 and angolo_deviazione > soglia_conferma:
                passaggio_porta_idx = i
                if not passaggio_confermato:
                    passaggio_confermato = True
                    direzione = "Uscita" if angles[i] > ANGOLO_RIPOSO else "Ingresso"
                    print(f"Debug: Passaggio confermato ({direzione}) al campione {i}")
            if detect_idx == -1 and detect[i] == 1:
                detect_idx = i
            if infrared_idx == -1 and infrared[i] == 1:
                infrared_idx = i

            if trigger:
                conteggio_senza_trigger = 0
                ultimo_trigger_idx = i
            else:
                conteggio_senza_trigger += 1

            # Chiusura forzata dell'evento se newcode == 1
            if newcode[i] == 1:
                fine_evento_idx = i
                durata_effettiva = (i - indice_inizio) * 0.1
                durata_totale = (tempi[fine_evento_idx] - timestamp_inizio).total_seconds()
                tipo = direzione if passaggio_confermato else "Affaccio"
                trigger_porta_t = (trigger_porta_idx - indice_inizio) * 0.1 if trigger_porta_idx != -1 else -1
                passaggio_porta_t = (passaggio_porta_idx - indice_inizio) * 0.1 if passaggio_porta_idx != -1 else -1
                detect_t = (detect_idx - indice_inizio) * 0.1 if detect_idx != -1 else -1
                infrared_t = (infrared_idx - indice_inizio) * 0.1 if infrared_idx != -1 else -1
                log.append({
                    "testo": f"{timestamp_inizio.strftime('%Y-%m-%d %H:%M:%S')} - {tipo} - Durata: {durata_effettiva:.2f} s - "
                             f"TriggerPorta: {trigger_porta_t:.1f} - PassaggioPorta: {passaggio_porta_t:.1f} - "
                             f"Detect: {detect_t:.1f} - Infrared: {infrared_t:.1f}",
                    "timestamp_inizio": timestamp_inizio,
                    "durata_totale": durata_totale,
                    "durata_effettiva": durata_effettiva
                })
                print(f"Debug: Evento chiuso forzatamente per newcode a {tempi[i]}, log: {log[-1]['testo']}")
                # Inizia un nuovo evento nello stesso campione
                stato = "IDLE"
                if trigger:  # Se c'è ancora un trigger, inizia subito un nuovo evento
                    stato = "EVENTO_ATTIVO"
                    timestamp_inizio = tempi[i]
                    indice_inizio = i
                    passaggio_confermato = False
                    direzione = None
                    conteggio_senza_trigger = 0
                    trigger_porta_idx = i if angolo_deviazione > soglia_trigger else -1
                    passaggio_porta_idx = -1
                    detect_idx = i if detect[i] == 1 else -1
                    infrared_idx = i if infrared[i] == 1 else -1
                    ultimo_trigger_idx = i
                    print(f"Debug: Nuovo evento iniziato per newcode a {timestamp_inizio}")

            elif conteggio_senza_trigger >= k:
                fine_evento_idx = i
                durata_effettiva = (ultimo_trigger_idx + 1 - indice_inizio) * 0.1
                durata_totale = (tempi[fine_evento_idx] - timestamp_inizio).total_seconds()
                tipo = direzione if passaggio_confermato else "Affaccio"
                trigger_porta_t = (trigger_porta_idx - indice_inizio) * 0.1 if trigger_porta_idx != -1 else -1
                passaggio_porta_t = (passaggio_porta_idx - indice_inizio) * 0.1 if passaggio_porta_idx != -1 else -1
                detect_t = (detect_idx - indice_inizio) * 0.1 if detect_idx != -1 else -1
                infrared_t = (infrared_idx - indice_inizio) * 0.1 if infrared_idx != -1 else -1
                log.append({
                    "testo": f"{timestamp_inizio.strftime('%Y-%m-%d %H:%M:%S')} - {tipo} - Durata: {durata_effettiva:.2f} s - "
                             f"TriggerPorta: {trigger_porta_t:.1f} - PassaggioPorta: {passaggio_porta_t:.1f} - "
                             f"Detect: {detect_t:.1f} - Infrared: {infrared_t:.1f}",
                    "timestamp_inizio": timestamp_inizio,
                    "durata_totale": durata_totale,
                    "durata_effettiva": durata_effettiva
                })
                stato = "IDLE"
                conteggio_senza_trigger = 0
                passaggio_confermato = False
                direzione = None
                trigger_porta_idx = -1
                passaggio_porta_idx = -1
                detect_idx = -1
                infrared_idx = -1
                ultimo_trigger_idx = 0
                print(f"Debug: Evento terminato, log: {log[-1]['testo']}")

    if stato == "EVENTO_ATTIVO":
        fine_evento_idx = len(angles) - 1
        durata_effettiva = (ultimo_trigger_idx + 1 - indice_inizio) * 0.1
        durata_totale = (tempi[fine_evento_idx] - timestamp_inizio).total_seconds()
        tipo = direzione if passaggio_confermato else "Affaccio"
        trigger_porta_t = (trigger_porta_idx - indice_inizio) * 0.1 if trigger_porta_idx != -1 else -1
        passaggio_porta_t = (passaggio_porta_idx - indice_inizio) * 0.1 if passaggio_porta_idx != -1 else -1
        detect_t = (detect_idx - indice_inizio) * 0.1 if detect_idx != -1 else -1
        infrared_t = (infrared_idx - indice_inizio) * 0.1 if infrared_idx != -1 else -1
        log.append({
            "testo": f"{timestamp_inizio.strftime('%Y-%m-%d %H:%M:%S')} - {tipo} - Durata: {durata_effettiva:.2f} s - "
                     f"TriggerPorta: {trigger_porta_t:.1f} - PassaggioPorta: {passaggio_porta_t:.1f} - "
                     f"Detect: {detect_t:.1f} - Infrared: {infrared_t:.1f}",
            "timestamp_inizio": timestamp_inizio,
            "durata_totale": durata_totale,
            "durata_effettiva": durata_effettiva
        })
        print(f"Debug: Evento finale loggato: {log[-1]['testo']}")

    print(f"Debug: Analisi completata, {len(log)} eventi trovati")
    return log

def crea_gui_passaggi():
    """Crea la GUI per l'analisi dei passaggi con selezione directory."""
    print("Debug: Creazione GUI")
    try:
        root = tk.Tk()
        root.title("Analisi Passaggi Gattaiola")
        root.geometry("1400x900+0-50")

        frame_input = ttk.Frame(root, padding="10")
        frame_input.grid(row=0, column=0, sticky=(tk.W, tk.E))

        ttk.Label(frame_input, text="Directory:").grid(row=0, column=0, sticky=tk.W)
        entry_directory = ttk.Entry(frame_input, width=30)
        entry_directory.insert(0, r"D:\downloads\porta")
        entry_directory.grid(row=0, column=1, padx=5)
        ttk.Button(frame_input, text="Sfoglia", command=lambda: entry_directory.delete(0, tk.END) or entry_directory.insert(0, filedialog.askdirectory())).grid(row=0, column=2, padx=5)

        ttk.Label(frame_input, text="Soglia Trigger (gradi):").grid(row=0, column=3, sticky=tk.W)
        entry_trigger = ttk.Entry(frame_input, width=10)
        entry_trigger.insert(0, "10")
        entry_trigger.grid(row=0, column=4, padx=5)

        ttk.Label(frame_input, text="Soglia Conferma (gradi):").grid(row=0, column=5, sticky=tk.W)
        entry_conferma = ttk.Entry(frame_input, width=10)
        entry_conferma.insert(0, "60")
        entry_conferma.grid(row=0, column=6, padx=5)

        ttk.Label(frame_input, text="k (campioni):").grid(row=0, column=7, sticky=tk.W)
        entry_k = ttk.Entry(frame_input, width=10)
        entry_k.insert(0, "200")
        entry_k.grid(row=0, column=8, padx=5)

        mostra_soglie_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame_input, text="Mostra soglie e limiti", variable=mostra_soglie_var).grid(row=0, column=9, padx=5)

        mostra_legenda_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame_input, text="Mostra legenda", variable=mostra_legenda_var).grid(row=0, column=10, padx=5)

        ttk.Button(frame_input, text="Avvia", command=lambda: avvia_programma(entry_directory.get())).grid(row=0, column=11, padx=5)

        frame_grafico = ttk.Frame(root, padding="10")
        frame_grafico.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=1)

        frame_log = ttk.Frame(root, padding="10")
        frame_log.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        def avvia_programma(directory):
            print(f"Debug: Avvio programma con directory {directory}")
            try:
                for widget in frame_grafico.winfo_children():
                    widget.destroy()
                for widget in frame_log.winfo_children():
                    widget.destroy()

                file_pattern = os.path.join(directory, "porta_*.bin")
                files = glob.glob(file_pattern)
                if not files:
                    text_log = tk.Text(frame_log, height=15, width=120, font=("Courier", 10))
                    text_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
                    text_log.insert(tk.END, f"Errore: Nessun file trovato in {directory}\n")
                    print(f"Errore: Nessun file trovato in {directory}")
                    return
                
                files.sort(key=lambda x: datetime.strptime(os.path.basename(x)[6:-4], "%Y%m%d_%H%M%S"))
                print(f"Debug: Trovati {len(files)} file")
                
                all_infrared = []
                all_detect = []
                all_door_open = []
                all_newcode = []
                all_angles = []
                all_tempi = []
                
                for i, file_path in enumerate(files):
                    dati = leggi_file_porta(file_path)
                    if dati is None:
                        continue
                    num_campioni = 16384
                    timestamp_ultimo = dati["timestamp"]
                    tempi = calcola_timestamp_campioni(timestamp_ultimo, num_campioni)
                    
                    num_campioni_da_mantenere = num_campioni
                    if i < len(files) - 1:
                        prossimo_file = files[i + 1]
                        prossimo_timestamp = datetime.strptime(
                            os.path.basename(prossimo_file)[6:-4], "%Y%m%d_%H%M%S")
                        prossimo_timestamp_inizio = prossimo_timestamp - timedelta(seconds=1638.4)
                        t1_fine = tempi[-1]
                        t2_inizio = prossimo_timestamp_inizio
                        if t2_inizio < t1_fine:
                            secondi_sovrapposizione = (t1_fine - t2_inizio).total_seconds()
                            campioni_sovrapposizione = int(round(secondi_sovrapposizione / 0.1))
                            num_campioni_da_mantenere = num_campioni - campioni_sovrapposizione
                            print(f"Debug: Sovrapposizione di {secondi_sovrapposizione:.1f}s ({campioni_sovrapposizione} campioni) tra {file_path} e {prossimo_file}")
                        else:
                            gap_secondi = (t2_inizio - t1_fine).total_seconds()
                            print(f"Debug: Gap di {gap_secondi:.1f}s tra {file_path} e {prossimo_file}")
                            ultimo_campione = {
                                "infrared": dati["infrared"][-1],
                                "detect": dati["detect"][-1],
                                "door_open": dati["door_open"][-1],
                                "newcode": dati["newcode"][-1],
                                "angles": dati["angles"][-1],
                                "tempo": tempi[-1]
                            }
                            gap_dati = riempi_gap(ultimo_campione, gap_secondi)
                            if gap_dati:
                                all_infrared.append(gap_dati["infrared"])
                                all_detect.append(gap_dati["detect"])
                                all_door_open.append(gap_dati["door_open"])
                                all_newcode.append(gap_dati["newcode"])
                                all_angles.append(gap_dati["angles"])
                                all_tempi.append(gap_dati["tempi"])

                    if num_campioni_da_mantenere > 0:
                        all_infrared.append(dati["infrared"][:num_campioni_da_mantenere])
                        all_detect.append(dati["detect"][:num_campioni_da_mantenere])
                        all_door_open.append(dati["door_open"][:num_campioni_da_mantenere])
                        all_newcode.append(dati["newcode"][:num_campioni_da_mantenere])
                        all_angles.append(dati["angles"][:num_campioni_da_mantenere])
                        all_tempi.append(tempi[:num_campioni_da_mantenere])
                        print(f"Debug: Aggiunti {num_campioni_da_mantenere} campioni da {file_path}")
                
                if not all_infrared:
                    text_log = tk.Text(frame_log, height=15, width=120, font=("Courier", 10))
                    text_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
                    text_log.insert(tk.END, "Errore: Nessun dato valido caricato\n")
                    print("Errore: Nessun dato valido caricato")
                    return
                
                all_infrared = np.concatenate(all_infrared)
                all_detect = np.concatenate(all_detect)
                all_door_open = np.concatenate(all_door_open)
                all_newcode = np.concatenate(all_newcode)
                all_angles = np.concatenate(all_angles)
                all_tempi = np.concatenate(all_tempi)
                print(f"Debug: Buffer aggregati, lunghezza: {len(all_angles)} campioni")

                fig, ax = plt.subplots(figsize=(10, 5))
                ax.plot(all_tempi, all_angles, label="Angolo", color="blue")
                ax.plot(all_tempi, all_infrared * 10 + 10, label="Infrared", color="red", linestyle="-")
                ax.plot(all_tempi, all_detect * 10 + 30, label="Detect", color="green", linestyle="-")
                ax.plot(all_tempi, all_door_open * 10 + 50, label="Door Open", color="purple", linestyle="-")
                ax.plot(all_tempi, all_newcode * 10 + 70, label="Newcode", color="brown", linestyle="-")
                ax.xaxis.set_major_formatter(DateFormatter("%H:%M:%S"))
                ax.set_xlabel("Tempo (HH:MM:SS)")
                ax.set_ylabel("Valori")
                ax.set_title(f"Dati Porta Aggregati - Inizio: {all_tempi[0].strftime('%Y-%m-%d %H:%M:%S')}")
                
                soglie_linee = []
                if mostra_soglie_var.get():
                    soglia_trigger = float(entry_trigger.get())
                    soglia_conferma = float(entry_conferma.get())
                    soglie_linee.append(ax.axhline(180 + soglia_trigger, color="green", linestyle="--", label=f"Trigger +{soglia_trigger}°"))
                    soglie_linee.append(ax.axhline(180 - soglia_trigger, color="green", linestyle="--", label=f"Trigger -{soglia_trigger}°"))
                    soglie_linee.append(ax.axhline(180 + soglia_conferma, color="orange", linestyle="--", label=f"Conferma +{soglia_conferma}°"))
                    soglie_linee.append(ax.axhline(180 - soglia_conferma, color="orange", linestyle="--", label=f"Conferma -{soglia_conferma}°"))
                
                ax.legend(loc="upper right")
                ax.grid(True)
                fig.tight_layout()

                x_lim_original = (all_tempi[0], all_tempi[-1])

                canvas = FigureCanvasTkAgg(fig, master=frame_grafico)
                canvas.draw()
                canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

                toolbar = NavigationToolbar2Tk(canvas, frame_grafico)
                toolbar.update()
                canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

                text_log = tk.Text(frame_log, height=15, width=120, font=("Courier", 10))
                text_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
                scrollbar = ttk.Scrollbar(frame_log, orient=tk.VERTICAL, command=text_log.yview)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                text_log['yscrollcommand'] = scrollbar.set

                linee_evento = []

                def avvia_analisi():
                    print("Debug: Pulsante Start Analisi premuto")
                    try:
                        soglia_trigger = float(entry_trigger.get())
                        soglia_conferma = float(entry_conferma.get())
                        k = int(entry_k.get())
                        if soglia_trigger < 0 or soglia_conferma < 0 or k <= 0:
                            text_log.delete(1.0, tk.END)
                            text_log.insert(tk.END, "Errore: Inserire valori validi (soglie ≥ 0, k > 0)\n")
                            print("Debug: Input non validi")
                            return
                        text_log.delete(1.0, tk.END)
                        log = analizza_passaggi(all_angles, all_infrared, all_detect, all_door_open, all_newcode, all_tempi, soglia_trigger, soglia_conferma, k)
                        for evento in log:
                            text_log.insert(tk.END, evento["testo"] + "\n")
                        print("Debug: Log aggiornato nella text box")
                        
                        for linea in soglie_linee:
                            linea.remove()
                        soglie_linee.clear()
                        if mostra_soglie_var.get():
                            soglie_linee.append(ax.axhline(180 + soglia_trigger, color="green", linestyle="--", label=f"Trigger +{soglia_trigger}°"))
                            soglie_linee.append(ax.axhline(180 - soglia_trigger, color="green", linestyle="--", label=f"Trigger -{soglia_trigger}°"))
                            soglie_linee.append(ax.axhline(180 + soglia_conferma, color="orange", linestyle="--", label=f"Conferma +{soglia_conferma}°"))
                            soglie_linee.append(ax.axhline(180 - soglia_conferma, color="orange", linestyle="--", label=f"Conferma -{soglia_conferma}°"))
                        ax.get_legend().set_visible(mostra_legenda_var.get())
                        canvas.draw()
                    except ValueError:
                        text_log.delete(1.0, tk.END)
                        text_log.insert(tk.END, "Errore: Inserire valori numerici validi\n")
                        print("Debug: Errore nei valori numerici")

                def on_log_click(event):
                    try:
                        index = text_log.index(tk.CURRENT)
                        line_num = int(index.split('.')[0]) - 1
                        line = text_log.get(f"{line_num + 1}.0", f"{line_num + 1}.end")
                        if not line.strip():
                            return

                        for linea in linee_evento:
                            linea.remove()
                        linee_evento.clear()

                        log = analizza_passaggi(all_angles, all_infrared, all_detect, all_door_open, all_newcode, 
                                                all_tempi, float(entry_trigger.get()), float(entry_conferma.get()), int(entry_k.get()))
                        if line_num >= len(log):
                            print("Debug: Indice riga non valido:", line_num)
                            return

                        evento = log[line_num]
                        timestamp_inizio = evento["timestamp_inizio"]
                        durata_totale = evento["durata_totale"]
                        durata_effettiva = evento["durata_effettiva"]

                        left = timestamp_inizio - timedelta(seconds=1.0)
                        right = timestamp_inizio + timedelta(seconds=durata_totale + 1.0)

                        ax.set_xlim(left, right)
                        
                        if mostra_soglie_var.get():
                            linee_evento.append(ax.axvline(timestamp_inizio, color="black", linestyle=":", label="Start Evento"))
                            linee_evento.append(ax.axvline(timestamp_inizio + timedelta(seconds=durata_effettiva), 
                                                          color="black", linestyle=":", label="Stop Evento"))
                        ax.get_legend().set_visible(mostra_legenda_var.get())
                        canvas.draw()
                        print(f"Debug: Zoom su evento {timestamp_inizio}, durata totale {durata_totale}s, durata effettiva {durata_effettiva}s, limiti x: {left} - {right}")

                        text_log.tag_remove("highlight", "1.0", tk.END)
                        text_log.tag_add("highlight", f"{line_num + 1}.0", f"{line_num + 1}.end")
                        text_log.tag_configure("highlight", background="yellow")
                    except Exception as e:
                        print(f"Debug: Errore nel gestire il clic sul log: {e}")

                def aggiorna_soglie_e_limiti():
                    for linea in soglie_linee:
                        linea.remove()
                    soglie_linee.clear()
                    if mostra_soglie_var.get():
                        try:
                            soglia_trigger = float(entry_trigger.get())
                            soglia_conferma = float(entry_conferma.get())
                            soglie_linee.append(ax.axhline(180 + soglia_trigger, color="green", linestyle="--", label=f"Trigger +{soglia_trigger}°"))
                            soglie_linee.append(ax.axhline(180 - soglia_trigger, color="green", linestyle="--", label=f"Trigger -{soglia_trigger}°"))
                            soglie_linee.append(ax.axhline(180 + soglia_conferma, color="orange", linestyle="--", label=f"Conferma +{soglia_conferma}°"))
                            soglie_linee.append(ax.axhline(180 - soglia_conferma, color="orange", linestyle="--", label=f"Conferma -{soglia_conferma}°"))
                        except ValueError:
                            print("Debug: Errore nei valori delle soglie")
                    ax.get_legend().set_visible(mostra_legenda_var.get())
                    canvas.draw()
                    print("Debug: Soglie e limiti aggiornati")

                def aggiorna_legenda():
                    ax.get_legend().set_visible(mostra_legenda_var.get())
                    canvas.draw()
                    print("Debug: Legenda aggiornata")

                def ripristina_zoom():
                    ax.set_xlim(x_lim_original)
                    for linea in linee_evento:
                        linea.remove()
                    linee_evento.clear()
                    ax.get_legend().set_visible(mostra_legenda_var.get())
                    canvas.draw()
                    print("Debug: Zoom ripristinato ai limiti originali")

                mostra_soglie_var.trace("w", lambda *args: aggiorna_soglie_e_limiti())
                mostra_legenda_var.trace("w", lambda *args: aggiorna_legenda())

                text_log.bind("<Button-1>", on_log_click)
                ttk.Button(frame_input, text="Start Analisi", command=avvia_analisi).grid(row=0, column=12, padx=5)
                ttk.Button(frame_input, text="Ripristina Zoom", command=ripristina_zoom).grid(row=0, column=13, padx=5)

                print("Debug: GUI aggiornata con grafico e log") 
            
            except Exception as e:
                text_log = tk.Text(frame_log, height=15, width=120, font=("Courier", 10))
                text_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
                text_log.insert(tk.END, f"Errore durante il caricamento: {e}\n")
                print(f"Errore durante il caricamento: {e}")

        print("Debug: GUI avviata")
        root.mainloop()
    except Exception as e:
        print(f"Errore nella creazione della GUI: {e}")

if __name__ == "__main__":
    print("Debug: Avvio programma")
    try:
        crea_gui_passaggi()
    except Exception as e:
        print(f"Errore generale nell'esecuzione: {e}")