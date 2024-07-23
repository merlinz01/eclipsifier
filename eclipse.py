import datetime
import os
import sys

import yaml
from PIL import Image, ImageDraw, ImageEnhance
from PIL.ExifTags import Base
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QWidget,
)

from PIL import ImageQt  # isort:skip


class DraggableLabel(QLabel):
    """A QLabel that responds to mouse drag events. Used to drag the sun into position."""

    def __init__(self, ondrag=None):
        super().__init__()
        self.last_pos = None
        self.ondrag = ondrag

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if self.last_pos is None:
            return
        new_pos = event.globalPosition().toPoint()
        delta = new_pos - self.last_pos
        if self.ondrag:
            self.ondrag(delta)
        self.last_pos = new_pos


class EclipsePicture:
    """A class to represent an eclipse picture and its configuration."""

    def __init__(self, filename: str):
        self.filename = filename
        print("\rOpening image", filename, end="")
        self.image = Image.open(filename)
        self.date = datetime.datetime.strptime(self.image._getexif()[Base.DateTimeOriginal], "%Y:%m:%d %H:%M:%S")  # type: ignore
        self.loaded = False

        # The center of the sun
        self.cx = self.image.width // 2
        self.cy = self.image.height // 2

        # The rotation
        self.rotate = 0

        # The zoom
        self.zoom = 100

        # The size of the final image
        self.width = 640
        self.height = 640

        # The brightness and contrast
        self.brightness = 100
        self.contrast = 100

        # Whether to include this image in the final collage
        self.included = True

        # Cached images
        self._configured_image = None
        self._configured_image_best = {}
        self._configured_image_small = None

    def invalidate(self):
        """Invalidate the cached images."""
        self._configured_image = None
        self._configured_image_best = {}
        self._configured_image_small = None

    def adjust_brightness(self, image: Image.Image):
        """Adjust the brightness of the image according to the configuration."""
        if self.brightness == 100:
            return image
        enhancer = ImageEnhance.Brightness(image)
        return enhancer.enhance(self.brightness / 100)

    def adjust_contrast(self, image: Image.Image):
        """Adjust the contrast of the image according to the configuration."""
        if self.contrast == 100:
            return image
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(self.contrast / 100)

    def configured(self):
        """Return the image configured according to the current configuration, optimized for speed.
        Includes additional elements for alignment."""
        # Return the cached image if available
        if self._configured_image:
            return self._configured_image

        print("\rConfiguring image", self.filename, end="")
        image = self.image

        # First crop to twice the desired size (without zooming)
        left = self.cx - self.width * (100 / self.zoom)
        top = self.cy - self.height * (100 / self.zoom)
        right = self.cx + self.width * (100 / self.zoom)
        bottom = self.cy + self.height * (100 / self.zoom)
        image = image.crop((int(left), int(top), int(right), int(bottom)))

        # Then stretch to twice the desired size
        image = image.resize((self.width, self.height), Image.Resampling.NEAREST)

        # Then rotate
        if self.rotate:
            image = image.rotate(
                self.rotate,
                Image.Resampling.NEAREST,
                center=(self.width / 2, self.height / 2),
            )

        # Then adjust brightness and contrast
        image = self.adjust_brightness(image)
        image = self.adjust_contrast(image)
        draw = ImageDraw.ImageDraw(image)

        # Draw a colored patch to adjust brightness by
        draw.rectangle(
            (
                self.width * 0.375,
                self.height * 0.375,
                self.width * 0.625,
                self.height * 0.625,
            ),
            fill=(223, 170, 113),
        )

        # Draw a circle to align the sun
        draw.ellipse(
            (
                self.width * 0.25,
                self.height * 0.25,
                self.width * 0.75,
                self.height * 0.75,
            ),
            outline="red",
        )

        # Draw a line to align the rotation of the moon's shadow
        draw.line(
            (0, self.height * 0.3, self.width, self.height * 0.7),
            fill="blue",
        )

        # Cache the configured image
        self._configured_image = image
        return image

    def configured_best(self, size=640):
        """Return the image configured according to the current configuration, optimized for quality."""
        # Return the cached image if available
        if self._configured_image_best.get(size, None):
            return self._configured_image_best[size]

        print("\rConfiguring best image", self.filename, end="")
        image = self.image

        # First crop to twice the desired size (without zooming)
        left = self.cx - self.width * 200 / self.zoom
        top = self.cy - self.height * 200 / self.zoom
        right = self.cx + self.width * 200 / self.zoom
        bottom = self.cy + self.height * 200 / self.zoom
        image = image.crop((int(left), int(top), int(right), int(bottom)))

        # Then stretch to twice the desired size
        image = image.resize((size * 2, size * 2), Image.Resampling.BICUBIC)

        # Then rotate
        if self.rotate:
            image = image.rotate(
                self.rotate,
                Image.Resampling.BICUBIC,
                center=(size, size),
            )

        # Then crop to the desired size
        left = size * 0.5
        top = size * 0.5
        right = size * 1.5
        bottom = size * 1.5
        image = image.crop((int(left), int(top), int(right), int(bottom)))

        # Then adjust brightness and contrast
        image = self.adjust_brightness(image)
        image = self.adjust_contrast(image)

        # Cache the configured image
        self._configured_image_best[size] = image
        return image

    def configured_small(self, size=20):
        """Return a small version of the image configured according to the current configuration."""
        # Return the cached image if available
        if self._configured_image_small:
            return self._configured_image_small

        print("\rConfiguring small image", self.filename, end="")
        image = self.image

        # First crop to the desired size (without zooming)
        left = self.cx - self.width * (50 / self.zoom)
        top = self.cy - self.height * (50 / self.zoom)
        right = self.cx + self.width * (50 / self.zoom)
        bottom = self.cy + self.height * (50 / self.zoom)
        image = image.crop((int(left), int(top), int(right), int(bottom)))

        # Then stretch to the desired size
        image = image.resize((size, size), Image.Resampling.NEAREST)

        # Then rotate
        if self.rotate:
            image = image.rotate(
                self.rotate,
                Image.Resampling.NEAREST,
                center=(size / 2, size / 2),
            )

        # Then adjust brightness and contrast
        image = self.adjust_brightness(image)
        image = self.adjust_contrast(image)

        # Cache the configured image
        self._configured_image_small = image
        return image

    def load_config(self):
        """Load the image configuration from a YAML file."""
        print("\rLoading image details", self.filename, end="")
        try:
            with open(self.filename + ".yml") as f:
                data: dict = yaml.safe_load(f)
                self.cx = data["cx"]
                self.cy = data["cy"]
                self.rotate = data["rotate"]
                self.zoom = data["zoom"]
                self.included = data.get("included", True)
                self.brightness = data.get("brightness", 100)
                self.contrast = data.get("contrast", 100)
            self.loaded = True
        except FileNotFoundError:
            pass

    def save_config(self):
        """Save the image configuration to a YAML file."""
        with open(self.filename + ".yml", "w") as f:
            yaml.dump(
                {
                    "cx": self.cx,
                    "cy": self.cy,
                    "rotate": self.rotate,
                    "zoom": self.zoom,
                    "included": self.included,
                    "brightness": self.brightness,
                    "contrast": self.contrast,
                },
                f,
            )


class Collage:
    """A class to render a collage of eclipse images."""

    def __init__(
        self,
        images: list[EclipsePicture],
        img_size=640,
        width=5760,
        height=5440,
        central_index=0,
    ):
        # The images to include in the collage
        self.images = images

        # The size of each image
        self.img_size = img_size

        # The size of the collage
        self.width = width
        self.height = height

        # The index of the central image
        self.central_index = central_index

    def render(self):
        """Render the collage."""
        collage = Image.new("RGB", (self.width, self.height), "white")
        x = 0
        y = 0
        i = 0
        for image in self.images:
            if not image.included:
                continue
            s = self.img_size
            if i == self.central_index:
                s = self.width
            img = image.configured_best(s)
            collage.paste(img, (x, y))
            x += img.width
            if x >= self.width:
                x = 0
                y += img.height
            i += 1
        return collage


class ImageTimeline(QGraphicsView):
    """A QGraphicsView to display a list of eclipse images spaced according to the time they were taken."""

    def __init__(self):
        super().__init__()
        self.scene_ = QGraphicsScene()
        self.setScene(self.scene_)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    def set_images(self, images: list[EclipsePicture]):
        """Update the list of images to display."""
        self.scene_.clear()
        starttime = None
        for i, image in enumerate(images):
            if starttime is None:
                starttime = image.date.timestamp()
                y = 0
            else:
                y = (image.date.timestamp() - starttime) / 5
            if not image.included:
                continue
            item = self.scene_.addText(image.date.strftime("%H:%M:%S"))
            item.setPos(10, y)
            pyimg = image.configured_small(20)
            image = ImageQt.ImageQt(pyimg)
            pixmap = QPixmap.fromImage(image)
            item = self.scene_.addPixmap(pixmap)
            item.setPos(100, y)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)


class Eclipsifier(QMainWindow):
    """The main window of the application."""

    def __init__(self, base_dir="eclipse"):
        super().__init__()

        self.base_dir = base_dir

        self.setWindowTitle("Eclipsifier")
        self.setGeometry(100, 100, 1500, 800)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout_ = QHBoxLayout()
        self.central_widget.setLayout(self.layout_)

        self.parameters_layout = QFormLayout()
        self.layout_.addLayout(self.parameters_layout)

        self.icon_list = QListWidget()
        self.icon_list.currentItemChanged.connect(self.show_image)
        self.parameters_layout.addRow(self.icon_list)

        self.cx = QSpinBox()
        self.cx.setRange(0, 10000)
        self.cx.setSingleStep(10)
        self.cx.valueChanged.connect(self.update_parameters)
        self.parameters_layout.addRow("Center X", self.cx)

        self.cy = QSpinBox()
        self.cy.setRange(0, 10000)
        self.cy.setSingleStep(10)
        self.cy.valueChanged.connect(self.update_parameters)
        self.parameters_layout.addRow("Center Y", self.cy)

        self.rotate = QSpinBox()
        self.rotate.setRange(-180, 180)
        self.rotate.setWrapping(True)
        self.rotate.valueChanged.connect(self.update_parameters)
        self.parameters_layout.addRow("Rotate", self.rotate)

        self.zoom = QSpinBox()
        self.zoom.setSuffix("%")
        self.zoom.setRange(10, 1000)
        self.zoom.valueChanged.connect(self.update_parameters)
        self.parameters_layout.addRow("Zoom", self.zoom)

        self.brightness = QSpinBox()
        self.brightness.setSuffix("%")
        self.brightness.setRange(10, 190)
        self.brightness.valueChanged.connect(self.update_parameters)
        self.parameters_layout.addRow("Brightness", self.brightness)

        self.contrast = QSpinBox()
        self.contrast.setSuffix("%")
        self.contrast.setRange(10, 190)
        self.contrast.valueChanged.connect(self.update_parameters)
        self.parameters_layout.addRow("Contrast", self.contrast)

        self.include = QCheckBox("\nInclude in collage\n")
        self.include.checkStateChanged.connect(self.update_parameters)
        self.parameters_layout.addRow(self.include)

        self.best = QCheckBox("Render best quality")
        self.best.checkStateChanged.connect(self.showit)
        self.parameters_layout.addRow(self.best)

        save = QPushButton("\n\nSave\n\n")
        save.clicked.connect(self.save)
        self.parameters_layout.addRow(save)

        self.image_label = DraggableLabel(self.ondrag)
        self.layout_.addWidget(self.image_label)

        self.timeline = ImageTimeline()
        self.layout_.addWidget(self.timeline)

        self.collage_layout = QFormLayout()
        self.layout_.addLayout(self.collage_layout)

        self.collage_width = QSpinBox()
        self.collage_width.setRange(100, 10000)
        self.collage_width.setValue(5760)
        self.collage_layout.addRow("Width", self.collage_width)

        self.collage_height = QSpinBox()
        self.collage_height.setRange(100, 10000)
        self.collage_height.setValue(5760)
        self.collage_layout.addRow("Height", self.collage_height)

        self.collage_image_size = QSpinBox()
        self.collage_image_size.setRange(100, 10000)
        self.collage_image_size.setValue(640)
        self.collage_layout.addRow("Individual Image Size", self.collage_image_size)

        self.collage_central = QSpinBox()
        self.collage_central.setRange(0, 1000)
        self.collage_central.setValue(0)
        self.collage_layout.addRow("Central Image Index", self.collage_central)

        self.collage_button = QPushButton("Generate Collage")
        self.collage_button.clicked.connect(self.show_collage)
        self.collage_layout.addRow(self.collage_button)

        self.collage_image = QLabel()
        self.collage_layout.addRow(self.collage_image)

        self.save_collageb = QPushButton("Save Collage")
        self.save_collageb.clicked.connect(self.save_collage)
        self.collage_layout.addRow(self.save_collageb)

        self.statusbar = self.statusBar()
        self.statusbar.showMessage("Image Viewer")

        self.configuring = False
        self.load_images()

    def load_images(self):
        """Load the images from the base directory."""
        # Add image paths to the list
        image_paths = os.listdir(self.base_dir)
        image_paths.sort()
        self.images = []
        for path in image_paths:
            if path.endswith(".yml"):
                continue
            self.statusbar.showMessage(f"Loading {path}")
            image = EclipsePicture(os.path.join(self.base_dir, path))
            image.load_config()
            self.images.append(image)
            item = QListWidgetItem(f'{image.date.strftime("%H:%M:%S")} {path}')
            if image.loaded:
                item.setBackground(
                    QColor("green") if image.included else QColor("darkgreen")
                )
            item._image = image  # type: ignore
            self.icon_list.addItem(item)
        self.timeline.set_images(self.images)
        self.statusbar.showMessage(f"Loaded {len(self.images)} images")

    def show_image(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        """Show the selected image."""
        self.current_image: EclipsePicture = current_item._image  # type: ignore
        self.showit()
        # Update the inputs with the current image's configuration
        self.configuring = True
        self.cx.setValue(self.current_image.cx)
        self.cy.setValue(self.current_image.cy)
        self.rotate.setValue(self.current_image.rotate)
        self.zoom.setValue(self.current_image.zoom)
        self.brightness.setValue(self.current_image.brightness)
        self.contrast.setValue(self.current_image.contrast)
        self.include.setCheckState(
            Qt.CheckState.Checked
            if self.current_image.included
            else Qt.CheckState.Unchecked
        )
        self.configuring = False

    def update_parameters(self):
        """Update the current image's configuration with the values from the inputs, and show the image."""
        if self.configuring:
            return
        self.current_image.cx = self.cx.value()
        self.current_image.cy = self.cy.value()
        self.current_image.rotate = self.rotate.value()
        self.current_image.zoom = self.zoom.value()
        self.current_image.included = self.include.checkState() == Qt.CheckState.Checked
        self.current_image.brightness = self.brightness.value()
        self.current_image.contrast = self.contrast.value()
        self.current_image.invalidate()
        self.timeline.set_images(self.images)
        self.showit()

    def showit(self, *args):
        """Show the current image."""
        try:
            if self.best.checkState() == Qt.CheckState.Checked:
                pyimg = self.current_image.configured_best()
            else:
                pyimg = self.current_image.configured()
            image = ImageQt.ImageQt(pyimg)
            pixmap = QPixmap.fromImage(image)
            self.image_label.setPixmap(pixmap)
        except Exception as e:
            print(e)
            self.statusbar.showMessage(str(e))

    def ondrag(self, delta):
        """Handle dragging the sun into position."""
        self.current_image.cx -= delta.x() * (100 / self.current_image.zoom)
        self.current_image.cy -= delta.y() * (100 / self.current_image.zoom)
        self.current_image.invalidate()
        self.showit()
        self.configuring = True
        self.cx.setValue(self.current_image.cx)
        self.cy.setValue(self.current_image.cy)
        self.configuring = False

    def show_collage(self):
        """Generate and show the collage."""
        cw = self.collage_width.value()
        ch = self.collage_height.value()
        if cw < ch:
            vw = 640 * self.collage_width.value() // self.collage_height.value()
            vh = 640
        else:
            vw = 640
            vh = 640 * self.collage_height.value() // self.collage_width.value()
        collage = Collage(
            self.images,
            self.collage_image_size.value(),
            self.collage_width.value(),
            self.collage_height.value(),
            self.collage_central.value(),
        )
        collage_image = collage.render().resize((vw, vh), Image.Resampling.BICUBIC)
        image = ImageQt.ImageQt(collage_image)
        pixmap = QPixmap.fromImage(image)
        self.collage_image.setPixmap(pixmap)

    def save_collage(self):
        """Save the collage to a file."""
        collage = Collage(
            self.images,
            self.collage_image_size.value(),
            self.collage_width.value(),
            self.collage_height.value(),
            self.collage_central.value(),
        )
        collage_image = collage.render()
        collage_image.save("collage.png")

    def save(self):
        """Save the current image's configuration to a file."""
        self.current_image.save_config()
        self.icon_list.currentItem().setBackground(
            QColor("green") if self.current_image.included else QColor("darkgreen")
        )


if __name__ == "__main__":
    config = {
        "base_dir": "./eclipse",
    }
    try:
        config.update(yaml.safe_load(open("config.yml")))
    except FileNotFoundError:
        pass
    app = QApplication(sys.argv)
    viewer = Eclipsifier(config["base_dir"])
    viewer.show()
    sys.exit(app.exec())
