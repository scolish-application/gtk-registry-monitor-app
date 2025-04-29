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
        self.login_window.present()
    
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
            
            self.pubsub_thread = threading.Thread(target=listen_for_messages, daemon=True)
            self.pubsub_thread.start()
            
        except Exception as e:
            print(f"Redis connection error: {e}")


class LoginWindow(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application)
        self.app = application
        
        self.set_title("Schola Monitor - Login")
        self.set_default_size(400, 300)
        
        # Create a header bar
        header_bar = Adw.HeaderBar()
        
        # Add minimize button
        minimize_button = Gtk.Button()
        minimize_button.set_icon_name("window-minimize-symbolic")
        minimize_button.connect("clicked", self.on_minimize_clicked)
        
        # Main container
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.main_box.set_margin_top(32)
        self.main_box.set_margin_bottom(32)
        self.main_box.set_margin_start(32)
        self.main_box.set_margin_end(32)
        
        # Create a content box to center items
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        content_box.set_valign(Gtk.Align.CENTER)
        content_box.set_halign(Gtk.Align.CENTER)
        content_box.set_vexpand(True)
        content_box.set_hexpand(True)
        
        # Avatar
        avatar = Adw.Avatar(size=96, show_initials=False)
        content_box.append(avatar)
        
        # Welcome text
        welcome_label = Gtk.Label()
        welcome_label.set_markup("<span size='x-large'>Bem-vindo ao Schola Monitor</span>")
        content_box.append(welcome_label)
        
        # Username entry
        username_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        username_label = Gtk.Label(label="Nome de usuário", halign=Gtk.Align.START)
        self.username_entry = Gtk.Entry()
        username_box.append(username_label)
        username_box.append(self.username_entry)
        content_box.append(username_box)
        
        # Password entry
        password_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        password_label = Gtk.Label(label="Senha", halign=Gtk.Align.START)
        self.password_entry = Gtk.Entry()
        self.password_entry.set_visibility(False)
        self.password_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        password_box.append(password_label)
        password_box.append(self.password_entry)
        content_box.append(password_box)
        
        # Login button
        self.login_button = Gtk.Button(label="Entrar")
        self.login_button.connect("clicked", self.on_login_clicked)
        self.login_button.add_css_class("suggested-action")
        self.login_button.set_margin_top(10)
        content_box.append(self.login_button)
        
        # Error label
        self.error_label = Gtk.Label()
        self.error_label.add_css_class("error")
        content_box.append(self.error_label)
        
        # Add content to the main box
        self.main_box.append(content_box)
        
        # Create a box to hold everything
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root_box.append(header_bar)
        root_box.append(self.main_box)
        
        # Add to window
        self.set_content(root_box)
    
    def on_login_clicked(self, button):
        username = self.username_entry.get_text()
        password = self.password_entry.get_text()
        
        if not username or not password:
            self.error_label.set_text("Por favor, preencha todos os campos")
            return
        
        # Attempt login
        success, message = self.app.auth_service.login(username, password)
        
        if success:
            self.app.show_main_window()
        else:
            self.error_label.set_text(message)
    
    def on_minimize_clicked(self, button):
        self.minimize()


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application)
        self.app = application
        
        self.set_title("Schola Monitor - Registros")
        self.set_default_size(800, 600)
        
        # Create header bar with window controls
        header_bar = Adw.HeaderBar()
        
        # Add minimize button
        minimize_button = Gtk.Button()
        minimize_button.set_icon_name("window-minimize-symbolic")
        minimize_button.connect("clicked", self.on_minimize_clicked)
        header_bar.pack_start(minimize_button)
        
        # Add hide button (iconify)
        hide_button = Gtk.Button()
        hide_button.set_icon_name("window-restore-symbolic")
        hide_button.connect("clicked", self.on_hide_clicked)
        header_bar.pack_start(hide_button)
        
        # Setup main content
        self.main_layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Header with refresh button
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header_box.set_margin_top(24)
        header_box.set_margin_bottom(12)
        header_box.set_margin_start(24)
        header_box.set_margin_end(24)
        
        title_label = Gtk.Label()
        title_label.set_markup("<span size='x-large' weight='bold'>Registros de Entrada</span>")
        title_label.set_halign(Gtk.Align.START)
        title_label.set_hexpand(True)
        
        refresh_button = Gtk.Button()
        refresh_button.set_icon_name("view-refresh-symbolic")
        refresh_button.connect("clicked", self.on_refresh_clicked)
        refresh_button.set_valign(Gtk.Align.CENTER)
        
        header_box.append(title_label)
        header_box.append(refresh_button)
        
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
        content_box.set_valign(Gtk.Align.CENTER)
        
        # Create scrolled window for list box
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        
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
                empty_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                empty_box.set_margin_top(12)
                empty_box.set_margin_bottom(12)
                empty_box.set_margin_start(12)
                empty_box.set_margin_end(12)
                
                empty_label = Gtk.Label(label="Não há registros de entrada disponíveis")
                empty_box.append(empty_label)
                empty_row.set_child(empty_box)
                self.list_box.append(empty_row)
            else:
                # Add each entry to the list
                for entry in entries:
                    row = Gtk.ListBoxRow()
                    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                    box.set_margin_top(12)
                    box.set_margin_bottom(12)
                    box.set_margin_start(12)
                    box.set_margin_end(12)
                    
                    # User info
                    user_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                    user_box.set_hexpand(True)
                    
                    name_label = Gtk.Label(label=entry["user"]["name"])
                    name_label.set_halign(Gtk.Align.START)
                    name_label.add_css_class("heading")
                    
                    time_label = Gtk.Label(label=entry["created"])
                    time_label.set_halign(Gtk.Align.START)
                    time_label.add_css_class("caption")
                    time_label.add_css_class("dim-label")
                    
                    user_box.append(name_label)
                    user_box.append(time_label)
                    
                    # Card color indicator
                    if "carte" in entry["user"] and entry["user"]["carte"]:
                        color = entry["user"]["carte"]["color"].lower()
                        color_box = Gtk.Box()
                        color_box.add_css_class(f"card-{color}")
                        color_box.set_size_request(24, 24)
                        box.append(color_box)
                    
                    box.append(user_box)
                    row.set_child(box)
                    self.list_box.append(row)
                
        except Exception as e:
            print(f"Error refreshing entries: {e}")
            error_row = Gtk.ListBoxRow()
            error_label = Gtk.Label(label=f"Erro ao carregar registros: {str(e)}")
            error_row.set_child(error_label)
            self.list_box.append(error_row)
        
        self.show_notification("Registros atualizados")
    
    def on_refresh_clicked(self, button):
        self.refresh_entries()
    
    def show_notification(self, message):
        toast = Adw.Toast.new(message)
        toast.set_timeout(2)
        self.toast_overlay.add_toast(toast)
    
    def on_minimize_clicked(self, button):
        self.minimize()
    
    def on_hide_clicked(self, button):
        self.iconify()


def main():
    # Carregar CSS
    css_provider = Gtk.CssProvider()
    try:
        css_provider.load_from_path("style.css")
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    except Exception as e:
        print(f"Erro ao carregar CSS: {e}")
    
    app = Application()
    return app.run(None)

if __name__ == "__main__":
    main()