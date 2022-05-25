# This code is based on Adafruit's PyPortal User Interface code https://learn.adafruit.com/making-a-pyportal-user-interface-displayio/the-full-code
# SPDX-FileCopyrightText: 2020 Richard Albritton for Adafruit Industries
# SPDX-License-Identifier: MIT

import time
import board
import microcontroller
import displayio
import busio
from analogio import AnalogIn
import neopixel
import adafruit_adt7410
import adafruit_lidarlite
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text.label import Label
from adafruit_button import Button
import adafruit_touchscreen
from adafruit_pyportal import PyPortal
from digitalio import DigitalInOut
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_requests as requests

pyportal = PyPortal()
pyportal.network.connect()

key = "rx"
latest_id = "rx"

# ------------- Inputs and Outputs Setup ------------- #
try:  # attempt to init. the temperature sensor
    i2c_bus = busio.I2C(board.SCL, board.SDA)
    adt = adafruit_adt7410.ADT7410(i2c_bus, address=0x48)
    adt.high_resolution = True

except ValueError:
    # Did not find ADT7410. Probably running on Titano or Pynt
    adt = None

# init. the light sensor
light_sensor = AnalogIn(board.LIGHT)

pixel_pin = board.D3
num_pixels = 1
ORDER = neopixel.RGB

pixels = neopixel.NeoPixel(
    pixel_pin, num_pixels, brightness=0.2, auto_write=True, pixel_order=ORDER
)

# ---------- Sound Effects ------------- #
soundDemo = '/sounds/sound.wav'
soundBeep = '/sounds/beep.wav'
soundTab = '/sounds/tab.wav'

# ------------- Screen Setup ------------- #
display = board.DISPLAY
display.rotation = 0

# Backlight function
# Value between 0 and 1 where 0 is OFF, 0.5 is 50% and 1 is 100% brightness.
def set_backlight(val):
    val = max(0, min(1.0, val))
    board.DISPLAY.auto_brightness = False
    board.DISPLAY.brightness = val

# Set the Backlight
set_backlight(0.7)

# Touchscreen setup
# -------Rotate 0:
screen_width = 320
screen_height = 240
ts = adafruit_touchscreen.Touchscreen(board.TOUCH_XL, board.TOUCH_XR,
                                      board.TOUCH_YD, board.TOUCH_YU,
                                      calibration=((5200, 59000), (5800, 57000)),
                                      size=(320, 240))


# ------------- Display Groups ------------- #
splash = displayio.Group(max_size=15)  # The Main Display Group
view1 = displayio.Group(max_size=15)  # Group for View 1 objects
view2 = displayio.Group(max_size=15)  # Group for View 2 objects
view3 = displayio.Group(max_size=15)  # Group for View 3 objects

def hideLayer(hide_target):
    try:
        splash.remove(hide_target)
    except ValueError:
        pass

def showLayer(show_target):
    try:
        time.sleep(0.1)
        splash.append(show_target)
    except ValueError:
        pass

# ------------- Setup for Images ------------- #

# Display an image until the loop starts
pyportal.set_background('/images/loading.bmp')


bg_group = displayio.Group(max_size=1)
splash.append(bg_group)


icon_group = displayio.Group(max_size=1)
icon_group.x = 15
icon_group.y = 35
icon_group.scale = 1
view2.append(icon_group)

# This will handel switching Images and Icons
def set_image(group, filename):
    """Set the image file for a given group for display.
    This is most useful for Icons or image slideshows.
        :param group: The chosen group
        :param filename: The filename of the chosen image
    """
    print("Set image to ", filename)
    if group:
        group.pop()

    if not filename:
        return  # we're done, no icon desired

    image_file = open(filename, "rb")
    image = displayio.OnDiskBitmap(image_file)
    try:
        image_sprite = displayio.TileGrid(image, pixel_shader=displayio.ColorConverter())
    except TypeError:
        image_sprite = displayio.TileGrid(image, pixel_shader=displayio.ColorConverter(),
                                          position=(0, 0))
    group.append(image_sprite)

set_image(bg_group, "/images/BGimage.bmp")

# ---------- Text Boxes ------------- #
# Set the font and preload letters
font1 = bitmap_font.load_font("/fonts/Federation-22.bdf")
font = bitmap_font.load_font("/fonts/StarFleet-24.bdf")
font.load_glyphs(b'abcdefghjiklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890- ()')

# Default Label styling:
TABS_X = 5
TABS_Y = 50

# Text Label Objects
sensors_label1 = Label(font1, text="", color=0x03AD31, max_glyphs=200)
sensors_label1.x = TABS_X+20
sensors_label1.y = TABS_Y
view1.append(sensors_label1)

sensor_data1 = Label(font1, text="Accessing . . .", color=0x03AD31, max_glyphs=100)
sensor_data1.x = TABS_X+15
sensor_data1.y = 120
view1.append(sensor_data1)

feed2_label = Label(font1, text="Text Wondow 2", color=0xFFFFFF, max_glyphs=200)
feed2_label.x = TABS_X
feed2_label.y = TABS_Y
#view2.append(feed2_label)

sensors_label = Label(font1, text="Data View", color=0x03AD31, max_glyphs=200)
sensors_label.x = TABS_X+20
sensors_label.y = TABS_Y
view3.append(sensors_label)

sensor_data = Label(font1, text="Data View", color=0x03AD31, max_glyphs=100)
sensor_data.x = TABS_X+15
sensor_data.y = 65
view3.append(sensor_data)

text_hight = Label(font1, text="M", color=0x03AD31, max_glyphs=10)
# return a reformatted string with word wrapping using PyPortal.wrap_nicely
def text_box(target, top, string, max_chars):
    text = pyportal.wrap_nicely(string, max_chars)
    new_text = ""
    test = ""
    for w in text:
        new_text += '\n'+w
        test += 'M\n'
    text_hight.text = test  # Odd things happen without this
    glyph_box = text_hight.bounding_box
    target.text = ""  # Odd things happen without this
    target.y = int(glyph_box[3]/2)+top
    target.text = new_text

# ---------- Display Buttons ------------- #
# Default button styling:
BUTTON_HEIGHT = 40
BUTTON_WIDTH = 80

# We want three buttons across the top of the screen
TAPS_HEIGHT = 40
TAPS_WIDTH = int(screen_width/3)
TAPS_Y = 0

# We want two big buttons at the bottom of the screen
BIG_BUTTON_HEIGHT = int(screen_height/3.2)
BIG_BUTTON_WIDTH = int(screen_width/2)
BIG_BUTTON_Y = int(screen_height-BIG_BUTTON_HEIGHT)

# This group will make it easy for us to read a button press later.
buttons = []

# Main User Interface Buttons
button_view1 = Button(x=0, y=0,
                      width=TAPS_WIDTH, height=TAPS_HEIGHT,
                      label="HANDHELD", label_font=font, label_color=0xff7e00,
                      fill_color=0x5c5b5c, outline_color=0x767676,
                      selected_fill=0x1a1a1a, selected_outline=0x2e2e2e,
                      selected_label=0x525252)
buttons.append(button_view1)  # adding this button to the buttons group

button_view2 = Button(x=TAPS_WIDTH, y=0,
                      width=TAPS_WIDTH, height=TAPS_HEIGHT,
                      label="SUBSPACE", label_font=font, label_color=0xff7e00,
                      fill_color=0x5c5b5c, outline_color=0x767676,
                      selected_fill=0x1a1a1a, selected_outline=0x2e2e2e,
                      selected_label=0x525252)
buttons.append(button_view2)  # adding this button to the buttons group

button_view3 = Button(x=TAPS_WIDTH*2, y=0,
                      width=TAPS_WIDTH, height=TAPS_HEIGHT,
                      label="SENSORS", label_font=font, label_color=0xff7e00,
                      fill_color=0x5c5b5c, outline_color=0x767676,
                      selected_fill=0x1a1a1a, selected_outline=0x2e2e2e,
                      selected_label=0x525252)
buttons.append(button_view3)  # adding this button to the buttons group

button_switch = Button(x=0, y=BIG_BUTTON_Y,
                       width=BIG_BUTTON_WIDTH, height=BIG_BUTTON_HEIGHT,
                       label="Switch", label_font=font, label_color=0xff7e00,
                       fill_color=0x5c5b5c, outline_color=0x767676,
                       selected_fill=0x1a1a1a, selected_outline=0x2e2e2e,
                       selected_label=0x525252)
#buttons.append(button_switch)  # adding this button to the buttons group

button_2 = Button(x=BIG_BUTTON_WIDTH, y=BIG_BUTTON_Y,
                  width=BIG_BUTTON_WIDTH, height=BIG_BUTTON_HEIGHT,
                  label="Button", label_font=font, label_color=0xff7e00,
                  fill_color=0x5c5b5c, outline_color=0x767676,
                  selected_fill=0x1a1a1a, selected_outline=0x2e2e2e,
                  selected_label=0x525252)
#buttons.append(button_2)  # adding this button to the buttons group

# Add all of the main buttons to the splash Group
for b in buttons:
    splash.append(b)


# Make a button to change the icon image on view2
button_icon = Button(x=150, y=60,
                     width=BUTTON_WIDTH, height=BUTTON_HEIGHT,
                     label="Icon", label_font=font, label_color=0xffffff,
                     fill_color=0x8900ff, outline_color=0xbc55fd,
                     selected_fill=0x5a5a5a, selected_outline=0xff6600,
                     selected_label=0x525252, style=Button.ROUNDRECT)
#buttons.append(button_icon)  # adding this button to the buttons group

# Add this button to view2 Group
#view2.append(button_icon)

# Make a button to play a sound on view2
button_sound = Button(x=150, y=170,
                      width=BUTTON_WIDTH, height=BUTTON_HEIGHT,
                      label="Sound", label_font=font, label_color=0xffffff,
                      fill_color=0x8900ff, outline_color=0xbc55fd,
                      selected_fill=0x5a5a5a, selected_outline=0xff6600,
                      selected_label=0x525252, style=Button.ROUNDRECT)
#buttons.append(button_sound)  # adding this button to the buttons group

# Add this button to view2 Group
#view3.append(button_sound)

#pylint: disable=global-statement
def switch_view(what_view):
    global view_live
    if what_view == 1:
        hideLayer(view2)
        hideLayer(view3)
        button_view1.selected = False
        button_view2.selected = True
        button_view3.selected = True
        showLayer(view1)
        view_live = 1
        print("View1 On")
    elif what_view == 2:
        # global icon
        hideLayer(view1)
        hideLayer(view3)
        button_view1.selected = True
        button_view2.selected = False
        button_view3.selected = True
        showLayer(view2)
        view_live = 2
        print("View2 On")
    else:
        hideLayer(view1)
        hideLayer(view2)
        button_view1.selected = True
        button_view2.selected = True
        button_view3.selected = False
        showLayer(view3)
        view_live = 3
        print("View3 On")
#pylint: enable=global-statement

# Set veriables and startup states
button_view1.selected = False
button_view2.selected = True
button_view3.selected = True
showLayer(view1)
hideLayer(view2)
hideLayer(view3)

view_live = 1
icon = 1
icon_name = "Ruby"
button_mode = 1
switch_state = 0
button_switch.label = "OFF"
button_switch.selected = True

# Update out Labels with display text.
text_box(sensors_label1, TABS_Y,
         "Star Fleet Computer", 30)
text_box(sensors_label1, TABS_Y,
         ""
         .format(sensors_label1.bounding_box[2], sensors_label1.bounding_box[2]*2), 15)

text_box(feed2_label, TABS_Y, 'SubSpace Data', 18)

text_box(sensors_label, TABS_Y-20,
         "", 28)

board.DISPLAY.show(splash)

# ------------- Code Loop ------------- #
while True:
    touch = ts.touch_point
    sensor = adafruit_lidarlite.LIDARLite(i2c_bus)
    
    feed = pyportal.get_io_feed(key)
    client = pyportal.network._get_io_client()
    last = client.receive_data(key)
    the_id = last['id']
    
    if the_id != latest_id:
        print("New value:",last['value'])
        latest_id = the_id

    try:
        # We print tuples so you can plot with Mu Plotter
        print((sensor.distance,))
        if adt:  # Only if we have the temperature sensor
            tempC = adt.temperature
        tempC = microcontroller.cpu.temperature
    except RuntimeError as e:
        # If we get a reading error, just print it and keep truckin'
        print(e)
    # you can remove this for ultra-fast measurements!
    tempK = tempC + 273.15
    sensor_data.text = 'OBJ DISTANCE:\n{} cm\n\nUNIT TEMP:\n{} K'.format(sensor.distance, tempK)
    sensor_data1.text = (last['value'])

    # ------------- Handle Button Press Detection  ------------- #
    if touch:  # Only do this if the screen is touched
        # loop with buttons using enumerate() to number each button group as i
        for i, b in enumerate(buttons):
            if b.contains(touch):  # Test each button to see if it was pressed
                print('button%d pressed' % i)
                if i == 0 and view_live != 1:  # only if view1 is visable
                    pyportal.play_file(soundTab)
                    switch_view(1)
                    pixels.fill((0, 255, 0))
                    while ts.touch_point:
                        pass
                if i == 1 and view_live != 2:  # only if view2 is visable
                    pyportal.play_file(soundTab)
                    switch_view(2)
                    set_image(icon_group,"/images/Sensor-graphic-subspace.bmp")
                    pixels.fill((255, 0, 0))
                    while ts.touch_point:
                        pass
                if i == 2 and view_live != 3:  # only if view3 is visable
                    pyportal.play_file(soundTab)
                    switch_view(3)
                    pixels.fill((0, 0, 255))
                    while ts.touch_point:
                        pass
                if i == 3:
                    pyportal.play_file(soundBeep)
                    # Toggle switch button type
                    if switch_state == 0:
                        switch_state = 1
                        b.label = "ON"
                        b.selected = False
                        pixel.fill(WHITE)
                        print("Swich ON")
                    else:
                        switch_state = 0
                        b.label = "OFF"
                        b.selected = True
                        pixel.fill(BLACK)
                        print("Swich OFF")
                    # for debounce
                    while ts.touch_point:
                        pass
                    print("Swich Pressed")
                if i == 4:
                    pyportal.play_file(soundBeep)
                    # Momentary button type
                    b.selected = True
                    print('Button Pressed')
                    button_mode = numberUP(button_mode, 5)
                    if button_mode == 1:
                        pixel.fill(RED)
                    elif button_mode == 2:
                        pixel.fill(YELLOW)
                    elif button_mode == 3:
                        pixel.fill(GREEN)
                    elif button_mode == 4:
                        pixel.fill(BLUE)
                    elif button_mode == 5:
                        pixel.fill(PURPLE)
                    switch_state = 1
                    button_switch.label = "ON"
                    button_switch.selected = False
                    # for debounce
                    while ts.touch_point:
                        pass
                    print("Button released")
                    b.selected = False
                if i == 5 and view_live == 2:  # only if view2 is visable
                    pyportal.play_file(soundBeep)
                    b.selected = True
                    while ts.touch_point:
                        pass
                    print("Icon Button Pressed")
                    icon = numberUP(icon, 3)
                    if icon == 1:
                        icon_name = "Ruby"
                    elif icon == 2:
                        icon_name = "Gus"
                    elif icon == 3:
                        icon_name = "Billie"
                    b.selected = False
                    text_box(feed2_label, TABS_Y,
                             "Every time you tap the Icon button the icon image will \
change. Say hi to {}!".format(icon_name), 18)
                    set_image(icon_group, "/images/"+icon_name+".bmp")
                if i == 6 and view_live == 3:  # only if view3 is visable
                    b.selected = True
                    while ts.touch_point:
                        pass
                    print("Sound Button Pressed")
                    pyportal.play_file(soundDemo)
                    b.selected = False
