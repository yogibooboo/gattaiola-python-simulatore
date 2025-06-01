import tkinter as tk
from tkinter import filedialog, ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import analisiESP32
import correlazione
import os

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Analisi Segnale")

        # Variabili
        self.percorso_file_var = tk.StringVar()
        self.ax1 = None  # Inizializza ax1 come None
        self.canvas = None
        self.fig = None

        # GUI
        frame = tk.Frame(root)
        frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        tk.Label(frame, text="File .bin:").grid(row=0, column=0, sticky="w")
        tk.Entry(frame, textvariable=self.percorso_file_var, width=50).grid(row=0, column=1, padx=5)
        tk.Button(frame, text="Scegli File", command=self.scegli_file).grid(row=0, column=2)

        self.status_label = tk.Label(frame, text="Stato: In attesa")
        self.status_label.grid(row=1, column=0, columnspan=3, sticky="w")

        tk.Button(frame, text="Analizza", command=self.analizza_file).grid(row=2, column=0, pady=5)
        tk.Button(frame, text="Correlazione", command=self.esegui_correlazione).grid(row=2, column=1, pady=5)

        self.risultato_text = tk.Text(frame, height=10, width=60)
        self.risultato_text.grid(row=3, column=0, columnspan=3, pady=5)

    def scegli_file(self):
        file = filedialog.askopenfilename(filetypes=[("Binary files", "*.bin")])
        if file:
            self.percorso_file_var.set(file)
            self.status_label.config(text="Stato: File selezionato")

    def analizza_file(self):
        """Chiama la funzione di analisi a buffer scorrevole da analisiESP32.py."""
        print("Debug: Inizio analizza_file...")
        percorso_file = self.percorso_file_var.get()
        print(f"Debug: Percorso file: '{percorso_file}'")
        if not percorso_file or not os.path.exists(percorso_file):
            print("Debug: Errore: Nessun file selezionato o file non trovato")
            self.status_label.config(text="Errore: Nessun file selezionato o file non trovato")
            return None
        self.status_label.config(text="Stato: Analisi ESP32 in corso...")
        try:
            segnale_filtrato = analisiESP32.analizza_con_buffer_scorrevole(percorso_file, self.status_label)
            print(f"Debug: analizza_con_buffer_scorrevole completata, segnale_filtrato: {segnale_filtrato is not None}, lunghezza: {len(segnale_filtrato) if segnale_filtrato is not None else 'None'}")
            self.status_label.config(text="Stato: Analisi ESP32 completata")
            return segnale_filtrato
        except Exception as e:
            print(f"Debug: Errore in analizza_file: {e}")
            self.status_label.config(text=f"Errore: Analisi ESP32 fallita: {e}")
            return None

    def esegui_correlazione(self):
        """Esegue l'analisi ESP32 e poi la correlazione."""
        print("Debug: Inizio esecuzione correlazione...")
        try:
            print("Debug: Chiamo analizza_file...")
            segnale_filtrato = self.analizza_file()
            print(f"Debug: Analisi completata, segnale_filtrato: {segnale_filtrato is not None}, lunghezza: {len(segnale_filtrato) if segnale_filtrato is not None else 'None'}")
            print("Debug: Procedo con correlazione...")
            if segnale_filtrato is not None:
                print("Debug: Chiamo correlazione con segnale filtrato...")
                # Passa ax1_32 dall'analisi ESP32
                ax1_32 = analisiESP32.get_ax1_32()
                if ax1_32 is None:
                    print("Debug: ax1_32 non disponibile, uso ax1 principale")
                    if self.ax1 is None:
                        self.fig, self.ax1 = plt.subplots(figsize=(10, 6))
                        canvas = FigureCanvasTkAgg(self.fig, master=self.root)
                        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                        self.canvas = canvas
                    ax1_32 = self.ax1
                correlazione.correlazione_con_sequenza_nota(
                    self.percorso_file_var.get(), correlazione.BYTES_NOTI,
                    self.status_label, ax1_32, self.risultato_text, segnale_filtrato
                )
            else:
                print("Debug: Segnale filtrato non valido, provo con segnale grezzo...")
                ax1_32 = analisiESP32.get_ax1_32()
                if ax1_32 is None:
                    print("Debug: ax1_32 non disponibile, uso ax1 principale")
                    if self.ax1 is None:
                        self.fig, self.ax1 = plt.subplots(figsize=(10, 6))
                        canvas = FigureCanvasTkAgg(self.fig, master=self.root)
                        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                        self.canvas = canvas
                    ax1_32 = self.ax1
                correlazione.correlazione_con_sequenza_nota(
                    self.percorso_file_var.get(), correlazione.BYTES_NOTI,
                    self.status_label, ax1_32, self.risultato_text, None
                )
            print("Debug: Correlazione completata")
        except Exception as e:
            print(f"Debug: Errore in esegui_correlazione: {e}")
            self.status_label.config(text=f"Errore: Correlazione fallita: {e}")
            self.risultato_text.delete(1.0, tk.END)
            self.risultato_text.insert(tk.END, f"Errore: {e}\n")

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()