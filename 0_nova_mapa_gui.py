import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import shutil
import re
import threading
import subprocess
import sys

class NovaMapaGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Průvodce vytvořením nové mapy")
        self.root.geometry("600x650")

        # Rámec pro soubory
        frame_files = tk.LabelFrame(root, text="Soubory nové mapy", padx=10, pady=10)
        frame_files.pack(fill="x", padx=10, pady=5)

        tk.Label(frame_files, text="Vyberte jakýkoliv ze 4 potřebných souborů (.omap, .png, .pgw, .xml).\nZbytek se automaticky dohledá podle stejného názvu.", justify="left").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self.paths = {"omap": tk.StringVar(), "png": tk.StringVar(), "pgw": tk.StringVar(), "xml": tk.StringVar()}

        for i, ext in enumerate(["omap", "png", "pgw", "xml"]):
            tk.Label(frame_files, text=f".{ext} soubor:").grid(row=i+1, column=0, sticky="w")
            tk.Entry(frame_files, textvariable=self.paths[ext], width=45).grid(row=i+1, column=1, padx=5)
            tk.Button(frame_files, text="Procházet", command=lambda e=ext: self.browse_file(e)).grid(row=i+1, column=2, pady=2)

        # Rámec pro nastavení
        frame_settings = tk.LabelFrame(root, text="Nastavení", padx=10, pady=10)
        frame_settings.pack(fill="x", padx=10, pady=5)
        
        tk.Label(frame_settings, text="Ekvidistance (m):").grid(row=0, column=0, sticky="w", pady=2)
        self.eq_var = tk.StringVar(value="5.0")
        tk.Entry(frame_settings, textvariable=self.eq_var, width=10).grid(row=0, column=1, padx=10, pady=2, sticky="w")

        tk.Label(frame_settings, text="Měřítko (např. 10000 pro 1:10 000):").grid(row=1, column=0, sticky="w", pady=2)
        self.scale_var = tk.StringVar(value="10000")
        tk.Entry(frame_settings, textvariable=self.scale_var, width=10).grid(row=1, column=1, padx=10, pady=2, sticky="w")

        # Spouštěcí tlačítko
        self.btn_run = tk.Button(root, text="Založit mapu a vygenerovat postupy", font=("Arial", 12, "bold"), bg="#4CAF50", fg="white", command=self.run_process)
        self.btn_run.pack(fill="x", padx=10, pady=10, ipady=5)

        # Logovací okno
        frame_log = tk.LabelFrame(root, text="Log / Výstup z generátoru", padx=10, pady=10)
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_widget = scrolledtext.ScrolledText(frame_log, bg="black", fg="white", font=("Consolas", 9))
        self.log_widget.pack(fill="both", expand=True)

    def log(self, text):
        self.log_widget.insert(tk.END, text + "\n")
        self.log_widget.see(tk.END)

    def browse_file(self, ext):
        file_path = filedialog.askopenfilename(filetypes=[(f"{ext.upper()} files", f"*.{ext}"), ("All files", "*.*")])
        if file_path:
            self.paths[ext].set(file_path)
            self.autofill_others(file_path)

    def autofill_others(self, selected_path):
        base_path, _ = os.path.splitext(selected_path)
        for ext in ["omap", "png", "pgw", "xml"]:
            candidate = f"{base_path}.{ext}"
            if os.path.exists(candidate) and not self.paths[ext].get():
                self.paths[ext].set(candidate)

    def run_process(self):
        # Validace
        for ext in ["omap", "png", "pgw", "xml"]:
            if not self.paths[ext].get() or not os.path.exists(self.paths[ext].get()):
                messagebox.showerror("Chyba", f"Chybí nebo neexistuje soubor .{ext}!\nVyberte prosím všechny 4 soubory.")
                return
        
        try:
            float(self.eq_var.get())
        except ValueError:
            messagebox.showerror("Chyba", "Ekvidistance musí být číslo (např. 5.0)!")
            return

        try:
            int(self.scale_var.get())
        except ValueError:
            messagebox.showerror("Chyba", "Měřítko musí být celé číslo (např. 10000)!")
            return

        self.btn_run.config(state="disabled")
        self.log_widget.delete(1.0, tk.END)
        threading.Thread(target=self._process_thread, daemon=True).start()

    def _process_thread(self):
        try:
            # 1. Kopirovani souboru
            self.log("=== 1. Kopírování souborů do projektu ===")
            project_dir = os.path.dirname(os.path.abspath(__file__))
            basenames = {}
            for ext in ["omap", "png", "pgw", "xml"]:
                src = self.paths[ext].get()
                dst = os.path.join(project_dir, os.path.basename(src))
                if src != dst:
                    self.log(f"Kopíruji: {os.path.basename(src)}")
                    shutil.copy2(src, dst)
                else:
                    self.log(f"Soubor {os.path.basename(src)} už je ve složce projektu.")
                basenames[ext] = os.path.basename(src)
            
            # 2. Uprava config.py
            self.log("\n=== 2. Zápis nastavení do config.py ===")
            config_path = os.path.join(project_dir, "config.py")
            with open(config_path, "r", encoding="utf-8") as f:
                config_content = f.read()

            config_content = re.sub(r'OMAP_FILE\s*=\s*".*?"', f'OMAP_FILE = "{basenames["omap"]}"', config_content)
            config_content = re.sub(r'PNG_FILE\s*=\s*".*?"', f'PNG_FILE  = "{basenames["png"]}"', config_content)
            config_content = re.sub(r'PGW_FILE\s*=\s*".*?"', f'PGW_FILE  = "{basenames["pgw"]}"', config_content)
            config_content = re.sub(r'XML_FILE\s*=\s*".*?"', f'XML_FILE  = "{basenames["xml"]}"', config_content)
            config_content = re.sub(r'EKVIDISTANCE_M\s*=\s*[\d\.]+', f'EKVIDISTANCE_M = {float(self.eq_var.get())}', config_content)
            config_content = re.sub(r'MAPA_MERITKO\s*=\s*[\d]+', f'MAPA_MERITKO = {int(self.scale_var.get())}', config_content)

            with open(config_path, "w", encoding="utf-8") as f:
                f.write(config_content)
            
            self.log("config.py úspěšně přepsán na novou mapu.")

            # Smazat starou kalibraci z cache aby se znovu vygenerovala? Ne, setup_mapa.py to udela samo jestli ma nove jmeno! 
            # (Vlastne nová mapa vytvoří novou podsložku v cache podle jména OMAP souboru, takže pohoda).

            # 3. Run setup_mapa.py
            self.log("\n=== 3. Extrakce a příprava mapy (setup_mapa.py) ===")
            self.run_subprocess([sys.executable, "-X", "utf8", "setup_mapa.py"])

            # 4. Run 3_auto_kalibrace.py
            self.log("\n=== 4. Automatická AI kalibrace obrazu (3_auto_kalibrace.py) ===")
            self.run_subprocess([sys.executable, "-X", "utf8", "3_auto_kalibrace.py"])

            # 5. Run 9_generator_postupu.py
            self.log("\n=== 5. Generování postupů (9_generator_postupu.py) ===")
            self.run_subprocess([sys.executable, "-X", "utf8", "9_generator_postupu.py"])

            self.log("\n===========================================================")
            self.log(" HOTOVO! Můžeš zavřít toto okno a pustit Kurátora:")
            self.log(" > python 10_kurator_nastroj.py")
            self.log("===========================================================")
            messagebox.showinfo("Hotovo", "Mapa byla úspěšně založena a postupy vygenerovány!\nNyní můžete otevřít Kurátora.")
            
        except Exception as e:
            self.log(f"\nCHYBA: {str(e)}")
            messagebox.showerror("Chyba běhu", f"Proces selhal s chybou:\n{str(e)}")
        finally:
            self.btn_run.config(state="normal")

    def run_subprocess(self, cmd):
        # Spusti proces a cte vystup po radcich
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            encoding='utf-8', 
            errors='replace',
            bufsize=1 # Line buffered
        )
        for line in iter(process.stdout.readline, ''):
            if line:
                self.log(line.rstrip())
        
        process.stdout.close()
        return_code = process.wait()
        
        if return_code != 0:
            raise Exception(f"Skript selhal s kódem {return_code}")

if __name__ == "__main__":
    root = tk.Tk()
    app = NovaMapaGUI(root)
    root.mainloop()
