import webbrowser
from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.core.window import Window

FRONTEND_URL = "http://localhost:3000"

class StageBridgeApp(App):
    def build(self):
        Window.size = (250, 100)
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        btn_open = Button(text='Open Web UI', size_hint=(1, 0.5))
        btn_quit = Button(text='Quit', size_hint=(1, 0.5))
        btn_open.bind(on_release=self.open_web_ui)
        btn_quit.bind(on_release=self.quit_app)
        layout.add_widget(btn_open)
        layout.add_widget(btn_quit)
        return layout

    def open_web_ui(self, instance):
        webbrowser.open(FRONTEND_URL)

    def quit_app(self, instance):
        self.stop()