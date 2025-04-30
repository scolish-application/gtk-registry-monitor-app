import gi
import json
import threading
import redis

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio, GObject, Gdk

from service.authentication_service import AuthService
from service.registration_service import RegistrationService

class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.github.simaodiazz.schola.monitor",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        
        # Services
        self.auth_service = AuthService()
        self.registration_service = RegistrationService()
        
        # Redis for notifications
        self.redis_client = None
        self.pubsub_thread = None
        
        # Connect to signals
        self.connect('activate', self.on_activate)
    
    def on_activate(self, app):
        # Show login window first
        self.login_window = LoginWindow(application=app)
        # Conectar o sinal de login bem-sucedido à função show_main_window
        self.login_window.connect("login-successful", self.on_login_successful)
        self.login_window.present()
    
    def on_login_successful(self, window):
        # Esta função será chamada quando o sinal login-successful for emitido
        self.show_main_window()
    
    def show_main_window(self):
        self.login_window.destroy()
        self.main_window = MainWindow(application=self)
        self.main_window.present()
        
        # Start listening for notifications
        self.start_redis_listener()
    
    def start_redis_listener(self):
        """Start Redis PubSub listener in a background thread"""
        try:
            self.redis_client = redis.Redis(host='localhost', port=6379, db=0)
            pubsub = self.redis_client.pubsub()
            pubsub.subscribe('notifications:registrations:new')
            
            def listen_for_messages():
                for message in pubsub.listen():
                    if message['type'] == 'message':
                        # Use GLib.idle_add to update UI from another thread
                        GLib.idle_add(self.main_window.refresh_entries)
                        GLib.idle_add(self.main_window.show_notification, "Novo registro detectado!")
            
            self.pubsub_thread = threading.Thread(target=listen_for_messages, daemon=True)
            self.pubsub_thread.start()
            
        except Exception as e:
            print(f"Redis connection error: {e}")


@Gtk.Template(filename='../ui/login_window.ui')
class LoginWindow(Adw.ApplicationWindow):
    __gtype_name__ = "LoginWindow"
    
    username_entry = Gtk.Template.Child()
    password_entry = Gtk.Template.Child()
    login_button = Gtk.Template.Child()
    error_label = Gtk.Template.Child()

    __gsignals__ = {
        "login-successful": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Login - Sistema de Gestão Escolar")
        self.set_default_size(400, 300)
        
        # Conectar sinais
        self.login_button.connect("clicked", self.on_login_clicked)
        self.username_entry.connect("activate", self.on_entry_activate)
        self.password_entry.connect("activate", self.on_entry_activate)
    
    def on_entry_activate(self, entry):
        self.on_login_clicked(None)
    
    def on_login_clicked(self, button):
        username = self.username_entry.get_text()
        password = self.password_entry.get_text()
        
        if not username or not password:
            self.error_label.set_text("Por favor, preencha todos os campos.")
            self.error_label.set_visible(True)
            return
        
        # Chama o serviço de autenticação
        success, message = AuthService.login(username, password)
        
        if success:
            # Emite o sinal de login bem-sucedido
            self.emit("login-successful")
        else:
            # Mostra a mensagem de erro
            self.error_label.set_text(message)
            self.error_label.set_visible(True)


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application)
        self.app = application
        
        self.set_title("Schola Monitor - Registros")
        self.set_default_size(800, 600)
        
        # Create header bar with window controls
        header_bar = Adw.HeaderBar()
        header_bar.set_title_widget(Adw.WindowTitle.new("Schola Monitor", "Sistema de Monitoramento"))
        
        # Add refresh button to header
        refresh_button = Gtk.Button()
        refresh_button.set_icon_name("view-refresh-symbolic")
        refresh_button.set_tooltip_text("Atualizar registros")
        refresh_button.connect("clicked", self.on_refresh_clicked)
        header_bar.pack_end(refresh_button)
        
        # Setup main content
        self.main_layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Header with title
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header_box.set_margin_top(24)
        header_box.set_margin_bottom(12)
        header_box.set_margin_start(24)
        header_box.set_margin_end(24)
        
        title_label = Gtk.Label()
        title_label.set_markup("<span size='x-large' weight='bold'>Registros de Entrada</span>")
        title_label.set_halign(Gtk.Align.START)
        title_label.set_hexpand(True)
        
        header_box.append(title_label)
        
        # Create toast overlay for notifications
        self.toast_overlay = Adw.ToastOverlay()
        
        # Create content area
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(24)
        content_box.set_margin_start(24)
        content_box.set_margin_end(24)
        content_box.set_vexpand(True)
        content_box.set_halign(Gtk.Align.FILL)
        content_box.set_valign(Gtk.Align.FILL)
        
        # Create scrolled window for list box
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_margin_top(4)
        
        # Status bar
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        status_box.set_margin_bottom(12)
        
        self.status_label = Gtk.Label(label="Carregando registros...")
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.add_css_class("caption")
        self.status_label.add_css_class("dim-label")
        status_box.append(self.status_label)
        
        content_box.append(status_box)
        
        # Registration list
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list_box.add_css_class("boxed-list")
        
        scrolled.set_child(self.list_box)
        content_box.append(scrolled)
        
        # Assemble the layout
        self.main_layout.append(header_box)
        self.main_layout.append(content_box)
        
        # Setup the toast overlay
        self.toast_overlay.set_child(self.main_layout)
        
        # Create a root box to hold everything
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root_box.append(header_bar)
        root_box.append(self.toast_overlay)
        
        # Add to window
        self.set_content(root_box)
        
        # Initial load of entries
        self.refresh_entries()
    
    def refresh_entries(self):
        """Refresh the list of registrations"""
        self.status_label.set_text("Atualizando registros...")
        
        # Clear existing entries
        while True:
            row = self.list_box.get_row_at_index(0)
            if row is None:
                break
            self.list_box.remove(row)
        
        # Get entries
        try:
            entries = self.app.registration_service.get_entry_registrations()
            
            if not entries:
                empty_row = Gtk.ListBoxRow()
                empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
                empty_box.set_margin_top(36)
                empty_box.set_margin_bottom(36)
                empty_box.set_margin_start(12)
                empty_box.set_margin_end(12)
                empty_box.set_halign(Gtk.Align.CENTER)
                
                # Empty state icon
                empty_icon = Gtk.Image.new_from_icon_name("system-search-symbolic")
                empty_icon.set_pixel_size(48)
                empty_icon.add_css_class("dim-label")
                
                empty_label = Gtk.Label(label="Não há registros de entrada disponíveis")
                empty_label.add_css_class("dim-label")
                
                empty_box.append(empty_icon)
                empty_box.append(empty_label)
                empty_row.set_child(empty_box)
                self.list_box.append(empty_row)
                
                self.status_label.set_text("Nenhum registro encontrado")
            else:
                # Add each entry to the list
                for entry in entries:
                    row = Gtk.ListBoxRow()
                    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
                    box.set_margin_top(16)
                    box.set_margin_bottom(16)
                    box.set_margin_start(16)
                    box.set_margin_end(16)
                    
                    # Card color indicator
                    card_color = "blue"  # Default color
                    if "carte" in entry["user"] and entry["user"]["carte"]:
                        card_color = entry["user"]["carte"]["color"].lower()
                    
                    color_box = Gtk.Box()
                    color_box.add_css_class(f"card-{card_color}")
                    color_box.set_size_request(16, 16)
                    color_box.set_valign(Gtk.Align.CENTER)
                    
                    # User avatar (initials)
                    user_name = entry["user"]["name"]
                    initials = "".join([name[0].upper() for name in user_name.split() if name])[:2]
                    avatar = Adw.Avatar(size=42, text=user_name, show_initials=True)
                    
                    # User info
                    user_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                    user_box.set_hexpand(True)
                    user_box.set_margin_start(12)
                    
                    name_label = Gtk.Label(label=user_name)
                    name_label.set_halign(Gtk.Align.START)
                    name_label.add_css_class("heading")
                    
                    time_label = Gtk.Label(label=entry["created"])
                    time_label.set_halign(Gtk.Align.START)
                    time_label.add_css_class("caption")
                    time_label.add_css_class("dim-label")
                    
                    user_box.append(name_label)
                    user_box.append(time_label)
                    
                    box.append(color_box)
                    box.append(avatar)
                    box.append(user_box)
                    
                    row.set_child(box)
                    self.list_box.append(row)
                
                self.status_label.set_text(f"{len(entries)} registros encontrados • Última atualização: agora")
                
        except Exception as e:
            print(f"Error refreshing entries: {e}")
            error_row = Gtk.ListBoxRow()
            error_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            error_box.set_margin_top(24)
            error_box.set_margin_bottom(24)
            error_box.set_margin_start(12)
            error_box.set_margin_end(12)
            error_box.set_halign(Gtk.Align.CENTER)
            
            error_icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
            error_icon.set_pixel_size(48)
            
            error_label = Gtk.Label()
            error_label.set_markup(f"<span color='#e74c3c'>Erro ao carregar registros:</span>\n{str(e)}")
            error_label.set_justify(Gtk.Justification.CENTER)
            
            error_box.append(error_icon)
            error_box.append(error_label)
            error_row.set_child(error_box)
            self.list_box.append(error_row)
            
            self.status_label.set_text("Erro ao carregar registros")
    
    def on_refresh_clicked(self, button):
        self.refresh_entries()
        self.show_notification("Registros atualizados")
    
    def show_notification(self, message):
        toast = Adw.Toast.new(message)
        toast.set_timeout(2)
        self.toast_overlay.add_toast(toast)
    
    def on_minimize_clicked(self, button):
        self.minimize()
    
    def on_hide_clicked(self, button):
        self.iconify()


def main():
    app = Application()
    return app.run(None)

if __name__ == "__main__":
    main()