"""Pixel alignment of the fixed page backdrop while child windows scroll."""
import os
import tkinter as tk
import unittest

from PIL import Image, ImageColor

from run_launcher import prepare_tk
from dekuforge.theme import BG, BackgroundCanvas, PagePanel


@unittest.skipUnless(os.name == 'nt', 'Windows desktop integration')
class ScrollingArtworkTests(unittest.TestCase):
    def setUp(self):
        prepare_tk()
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        self.root.geometry('740x520')
        self.surface = BackgroundCanvas(self.root)
        # Asymmetric synthetic artwork makes both vertical and horizontal drift visible.
        self.surface._art = Image.new('RGB', (740, 520))
        self.surface._art.putdata([((x * 3) % 256, (y * 5) % 256, (x + y * 2) % 256)
                                   for y in range(520) for x in range(740)])
        self.surface.pack(fill='both', expand=True)
        host = tk.Frame(self.surface)
        host.place(x=35, y=30, width=650, height=420)
        self.panel = PagePanel(host, self.surface)
        self.panel.pack(fill='both', expand=True)
        self.sections = []
        for _ in range(12):
            # A plain Frame deliberately separates these canvases from the body.
            wrapper = tk.Frame(self.panel.body)
            wrapper.pack(fill='x', pady=8)
            section = BackgroundCanvas(wrapper, surface=self.surface, opacity=.15, height=100)
            section.pack(fill='x')
            self.sections.append(section)
        self.root.update()
        self.surface._redraw()
        self.panel.viewport._redraw()

    def assert_backdrop_pixel(self, canvas, x, y):
        self.assertIsNotNone(canvas._image)
        left, top = canvas.coords(canvas._item)
        image_x = round(canvas.canvasx(x) - left)
        image_y = round(canvas.canvasy(y) - top)
        self.assertTrue(0 <= image_x < canvas._image.width() and 0 <= image_y < canvas._image.height())
        source_x = canvas.winfo_rootx() - self.surface.winfo_rootx() + x
        source_y = canvas.winfo_rooty() - self.surface.winfo_rooty() + y
        source = self.surface._fitted.getpixel((source_x, source_y))
        expected = Image.blend(Image.new('RGB', (1, 1), ImageColor.getrgb(BG)),
                               Image.new('RGB', (1, 1), source), canvas._opacity).getpixel((0, 0))
        self.assertEqual(canvas._image.get(image_x, image_y), expected)

    def assert_visible_artwork(self):
        viewport = self.panel.viewport
        self.assertEqual(tuple(viewport.coords(viewport._item)),
                         (viewport.canvasx(0), viewport.canvasy(0)))
        self.assert_backdrop_pixel(viewport, 5, 5)
        visible = 0
        for section in self.sections:
            y = max(5, viewport.winfo_rooty() - section.winfo_rooty() + 5)
            if y < section.winfo_height() - 5 and section.winfo_rooty() + y < viewport.winfo_rooty() + viewport.winfo_height() - 5:
                self.assert_backdrop_pixel(section, 5, y)
                visible += 1
        self.assertGreater(visible, 0)

    def test_scrollbar_wheel_and_focus_keep_the_artwork_fixed(self):
        viewport = self.panel.viewport
        for fraction in (.2, .7, 0, 1, .4):
            viewport.yview_moveto(fraction)
            self.root.update_idletasks()
            self.assert_visible_artwork()
        self.sections[5].event_generate('<MouseWheel>', delta=-120)
        self.root.update_idletasks()
        self.assert_visible_artwork()
        self.panel.reveal(self.sections[-1])
        self.root.update_idletasks()
        self.assert_visible_artwork()

    def test_background_resize_reaches_descendants_behind_plain_frames(self):
        self.panel.viewport.yview_moveto(.5)
        self.root.update_idletasks()
        self.surface._art = Image.new('RGB', (740, 520), '#c04090')
        self.surface._fitted = None
        self.surface._redraw()
        self.assert_visible_artwork()


@unittest.skipUnless(os.name == 'nt', 'Windows desktop integration')
class StretchedPanelTests(unittest.TestCase):
    """The build page's log view takes the height the window has left; taller content still scrolls."""
    def setUp(self):
        prepare_tk()
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        self.root.geometry('740x620')
        self.surface = BackgroundCanvas(self.root)
        self.surface.pack(fill='both', expand=True)
        host = tk.Frame(self.surface)
        host.place(x=35, y=30, width=650, height=560)
        self.panel = PagePanel(host, self.surface)
        self.panel.pack(fill='both', expand=True)
        tk.Label(self.panel.body, text='Title').pack(anchor='w')
        self.log = tk.Text(self.panel.body, height=7)
        self.log.pack(fill='both', expand=True)
        tk.Button(self.panel.body, text='Go').pack(anchor='e')
        self.root.update()

    def inner_height(self):
        return self.panel.viewport.winfo_height() - 2 * self.panel.padding

    def test_without_stretch_the_log_keeps_its_requested_height(self):
        self.assertEqual(self.log.winfo_height(), self.log.winfo_reqheight())
        self.assertLess(self.panel.body.winfo_height(), self.inner_height())

    def test_stretch_gives_the_free_height_to_the_expanding_log(self):
        before = self.log.winfo_height()
        self.panel.set_stretch()
        self.root.update()
        self.assertGreater(self.log.winfo_height(), before + 50)
        self.assertEqual(self.panel.body.winfo_height(), self.inner_height())

    def test_content_taller_than_the_window_still_scrolls(self):
        self.log.configure(height=60)
        self.panel.set_stretch()
        self.root.update()
        self.assertGreater(self.panel.body.winfo_reqheight(), self.inner_height())
        self.assertEqual(self.panel.body.winfo_height(), self.panel.body.winfo_reqheight())
        scrollregion = [int(part) for part in str(self.panel.viewport.cget('scrollregion')).split()]
        self.assertEqual(scrollregion[3], self.panel.body.winfo_reqheight() + 2 * self.panel.padding)
