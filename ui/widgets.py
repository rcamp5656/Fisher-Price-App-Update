"""
ui/widgets.py
Contains custom Kivy widgets and reusable UI helper functions.
"""
import random
import colorsys
from kivy.uix.spinner import Spinner
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button

def get_contrasting_colors(num_colors=49):
    """Generates a list of visually distinct colors."""
    colors = []
    for i in range(num_colors):
        hue = i / num_colors
        saturation = 0.6 + (i % 7) / 20.0
        value = 0.8 - (i % 5) / 10.0
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        colors.append((r, g, b, 1.0))
    random.shuffle(colors)
    return colors

def make_nav(buttons):
    """Creates a standard navigation bar from a list of (label, callback) tuples."""
    nav = BoxLayout(size_hint=(1, 0.1), spacing=4, padding=2)
    for label, callback in buttons:
        btn = Button(text=label, font_size=12, color=(1, 1, 1, 1), outline_color=(0, 0, 0, 1), outline_width=2)
        btn.bind(on_release=callback)
        nav.add_widget(btn)
    return nav

def split_filename(name, line_length=13, max_lines=10):
    """Splits a long filename into multiple lines for display on a button."""
    trimmed = name[:line_length * max_lines]
    lines = [trimmed[i:i + line_length] for i in range(0, len(trimmed), line_length)]
    return '\n'.join([f" {line} " for line in lines])

class MySpinner(Spinner):
    """A custom Spinner with a multi-column dropdown for better visibility."""
    def _fill_dropdown(self, *largs):
        self.dropdown.clear_widgets()
        grid = GridLayout(cols=4, spacing=5, padding=5, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        
        for value in self.values:
            btn = Button(
                text=value,
                size_hint_y=None,
                height=30,
                on_release=lambda instance: self.dropdown.select(instance.text)
            )
            grid.add_widget(btn)
        
        self.dropdown.add_widget(grid)