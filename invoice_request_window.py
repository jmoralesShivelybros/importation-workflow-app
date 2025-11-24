import tkinter as tk
from tkinter import ttk
import datetime
import os

class InvoiceRequestWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        
        # Configuración básica de la ventana
        self.title("Solicitud de Facturas")
        self.geometry("1000x600")

        # Hacer la ventana modal
        self.transient(parent)
        self.grab_set()
        
        # Lista completa de destinatarios
        self.recipients = {
            'to': [
                '"Cesar Cisneros" <ccisneros@omcdemexico.com>',
                '"Jose Inzunza - Omc Forwarding" <jinzunza@omcdemexico.com>',
                '"Alicia Martinez - OMC" <amartinez@omcdemexico.com>',
                '"Jannet Castillo" <jcastillo@omcdemexico.com>',
                '"slozano@omcdemexico.com" <slozano@omcdemexico.com>',
                '"Diana Lugo - OMC Forwarding" <dlugo@omcdemexico.com>',
                '"Patricia Ramos" <patricia.ramos@shivelybros.com>',
                '"Mayela Fuentes" <mayela.fuentes@shivelybros.com>',
                '"Yabel Caballero" <yabel.caballero@shivelybros.com>',
                '"Diana Charles" <diana.charles@shivelybros.com>',
                '"Alejandro Matta" <alejandro.matta@shivelybros.com>',
                '"operacion@omcdemexico.com" <operacion@omcdemexico.com>',
                '"srodriguezcoah@omcdemexico.com" <srodriguezcoah@omcdemexico.com>',
                '"Lucia Charles" <lucia.charles@shivelybros.com>',
                '"Dana Oropeza" <dana.oropeza@shivelybros.com>',
                '"Erika Jimenez" <erika.jimenez@shivelybros.com>',
                '"Fernanda Martinez" <Fernanda.Martinez@shivelybros.com>'
            ],
            'cc': [
                '"Cesar Cisneros" <ccisneros@omcdemexico.com>',
                '"Jose Inzunza - Omc Forwarding" <jinzunza@omcdemexico.com>',
                '"Alicia Martinez - OMC" <amartinez@omcdemexico.com>',
                '"Jannet Castillo" <jcastillo@omcdemexico.com>',
                '"slozano@omcdemexico.com" <slozano@omcdemexico.com>',
                '"Diana Lugo - OMC Forwarding" <dlugo@omcdemexico.com>',
                '"Patricia Ramos" <patricia.ramos@shivelybros.com>',
                '"Mayela Fuentes" <mayela.fuentes@shivelybros.com>',
                '"Yabel Caballero" <yabel.caballero@shivelybros.com>',
                '"Diana Charles" <diana.charles@shivelybros.com>',
                '"Alejandro Matta" <alejandro.matta@shivelybros.com>',
                '"operacion@omcdemexico.com" <operacion@omcdemexico.com>',
                '"srodriguezcoah@omcdemexico.com" <srodriguezcoah@omcdemexico.com>',
                '"Lucia Charles" <lucia.charles@shivelybros.com>',
                '"Dana Oropeza" <dana.oropeza@shivelybros.com>',
                '"Erika Jimenez" <erika.jimenez@shivelybros.com>',
                '"Fernanda Martinez" <Fernanda.Martinez@shivelybros.com>'
            ]
        }
        
        self.create_widgets()

    def create_widgets(self):
        # Main frame con PanedWindow vertical
        self.main_paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Frame superior para el email
        email_frame = ttk.LabelFrame(self.main_paned, text="Contenido del Email", padding="5")
        
        # Email text con scrollbar
        email_scroll = ttk.Scrollbar(email_frame)
        self.email_text = tk.Text(email_frame, wrap=tk.WORD, height=15, 
                                yscrollcommand=email_scroll.set)
        email_scroll.config(command=self.email_text.yview)
        
        self.email_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        email_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Frame para botones del email
        btn_frame = ttk.Frame(email_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Botón copiar
        copy_btn = ttk.Button(
            btn_frame,
            text="Copiar Contenido",
            command=self.copy_to_clipboard
        )
        copy_btn.pack(side=tk.RIGHT, padx=5)
        
        # Frame inferior para el explorador de archivos
        files_frame = ttk.LabelFrame(self.main_paned, text="Archivos OMC", padding="5")
        
        # Lista de archivos con scrollbars
        self.files_tree = ttk.Treeview(files_frame, columns=("name", "date"), show="headings")
        self.files_tree.heading("name", text="Nombre")
        self.files_tree.heading("date", text="Fecha modificación")
        
        # Configurar columnas
        self.files_tree.column("name", width=300)
        self.files_tree.column("date", width=150)
        
        # Scrollbars para la lista de archivos
        y_scroll = ttk.Scrollbar(files_frame, orient=tk.VERTICAL, command=self.files_tree.yview)
        x_scroll = ttk.Scrollbar(files_frame, orient=tk.HORIZONTAL, command=self.files_tree.xview)
        self.files_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        
        # Layout de la lista y scrollbars
        self.files_tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        
        # Configurar grid
        files_frame.grid_columnconfigure(0, weight=1)
        files_frame.grid_rowconfigure(0, weight=1)
        
        # Agregar frames al PanedWindow
        self.main_paned.add(email_frame, weight=1)
        self.main_paned.add(files_frame, weight=1)
        
        # Generar contenido del email
        self.generate_email_content()
        
        # Cargar archivos
        self.load_omc_files()
        
        # Doble clic para abrir archivo
        self.files_tree.bind('<Double-1>', self.open_file)

    def load_omc_files(self):
        try:
            week_num = self.parent.selected_week.get()
            omc_path = self.parent.folder_manager.get_omc_folder_path(week_num)
            
            if os.path.exists(omc_path):
                # Limpiar lista actual
                for item in self.files_tree.get_children():
                    self.files_tree.delete(item)
                
                # Agregar archivos
                for file in os.listdir(omc_path):
                    file_path = os.path.join(omc_path, file)
                    mod_time = datetime.datetime.fromtimestamp(
                        os.path.getmtime(file_path)
                    ).strftime('%Y-%m-%d %H:%M')
                    
                    self.files_tree.insert("", tk.END, values=(file, mod_time))
            else:
                print(f"La carpeta no existe: {omc_path}")
        except Exception as e:
            print(f"Error cargando archivos OMC: {str(e)}")

    def open_file(self, event):
        try:
            item = self.files_tree.selection()[0]
            file_name = self.files_tree.item(item, "values")[0]
            week_num = self.parent.selected_week.get()
            file_path = os.path.join(
                self.parent.folder_manager.get_omc_folder_path(week_num),
                file_name
            )
            if os.path.exists(file_path):
                os.startfile(file_path)
        except Exception as e:
            print(f"Error abriendo archivo: {str(e)}")

    def generate_email_content(self):
        current_date = datetime.datetime.now().strftime("%d/%m/%Y")
        email_content = f"""TO:
{'; '.join(self.recipients['to'])}

CC:
{'; '.join(self.recipients['cc'])}

Subject: FACTURAS IMPORTACION {current_date}

Could you help me with the invoices for importation

[Tabla de información pendiente]
"""
        self.email_text.delete('1.0', tk.END)
        self.email_text.insert('1.0', email_content)

    def copy_to_clipboard(self):
        content = self.email_text.get('1.0', tk.END)
        self.clipboard_clear()
        self.clipboard_append(content)