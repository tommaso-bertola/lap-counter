# `lap-counter` utility

>This utility is 99% AI generated, designed with Google Antigravity.
>The remaining 1% is the knowledge of the author of this utility and this README file.

# Purpose

The purpose of this utility is to listen to Wiclax passing events (when athletes pass through a checkpoint triggering a signal a.k.a. lap) and displaying it to the Microgate display.

It is specifically tailored to suit the needs to time the Hybrid Race format, where athletes lap 4 times a course, do an additional task (e.g. dumbbell lifts, ...) and then repeat the process until they have completed a total of 8 tasks.

It is designed to work with the `Graphic` protocol and was tested on the **Microtab Led Display** using .netBoards and a single physical display board.

When several athletes pass through the checkpoint at the same time, the utility will cycle through the athletes' bib numbers or surnames and associated `msg` (computed on Wiclax) on the display board, showing each row for a short period of time.

The time threshold for cycling through the athletes can be configured in the `config.json` file, the athlete identifier and `msg` can be customized inside of Wiclax.

A filter on the messages to display on the board is active and works by checking the `display` field in Wiclax, so that only the athletes that satisfy the criteria defined in Wiclax will be displayed on the board.
All other messages will be ignored by the utility and not sent to the display board.

Make sure to configure the right IP address and port for the Microgate display in the `config.json` file and the Wiclax server connection settings as well.

There is no need to interact with the utility directly, as it will automatically listen to the Wiclax events and update the display accordingly.

Some diagnostic logs are printed to the console for debugging purposes, but they can be ignored during normal operation.

# Installation

## From git via pip

`pip install git+https://github.com/tommaso-bertola/lap-counter.git@main`

Upgrade when new versions are released:
`pip install --upgrade git+https://github.com/tommaso-bertola/lap-counter.git@main`

To run the utility after installing via pip, simply run:
`lap-counter`

> Note: add the `config.json` file to the current working directory or set the `LAP_COUNTER_CONFIG` environment variable to the absolute path of the config file if you want to use a custom configuration. Otherwise, the utility will look for a user config file in the OS user config path and create it from the bundled default if it does not exist.

## Run from source

From the project root:

`PYTHONPATH=src python -m lap_counter.cli`

## Install as a package

From the project root:

`pip install .`

Then run:

`lap-counter`

# Configuration file location and priority

The app now supports packaged execution with a user-writable config file.

At startup, configuration is resolved in this order:

1. `LAP_COUNTER_CONFIG` environment variable (absolute path recommended)
2. local `config.json` in the current working directory
3. OS user config path (auto-created from packaged defaults if missing)

## macOS path

When installed as a package on macOS, edit this file:

`~/Library/Application Support/lap-counter/config.json`

If it does not exist, the app creates it automatically on first run using the bundled default configuration.

## Example override

`LAP_COUNTER_CONFIG=/absolute/path/to/config.json lap-counter`

# Usage task list

 1. Connect the display board on the `Base Program` and make sure it connects with a known IP address and port.
 Usually, the port is `21967` for the Microtab Led Display, but remember to check, the IP shall be configured according to your network settings and shall be in the same subnet of the Wiclax server.

 2. Open Wiclax and create the additional fields required to send the info to the utility.
 Remember to click `Apply` before creating the new fields, otherwise Wiclax will not be able to recognize the new fields in the formula editor.
    1. Create a `n_laps` field to count the number of laps for each athlete. This can vary based on the track length and race format specifics. For the Hybrid Race format, it should be set to 4 laps on a 200m track.
    Make sure it is a **numeric** field and available in the Results view.
    2. Create an `id` field to uniquely identify each athlete. This can be the `bib` field in Wiclax, or the athlete's name, or any other **unique identifier**.
    3. Create a `msg` field to compute the message to be displayed on the Microgate display. The forumla is as follows, but can be adapted to any visualization need.
    Make sure it is available in the Results view.
    4. Create a `display` field to define the criteria to display the athlete on the board. For example, you can set it to `True` for all the athletes that are entering the Exercise area, so that they will be displayed on the board as soon as they pass the checkpoint. Make sure it is available in the Results view.
 3. Enable the `Live` mode in Wiclax.
 4. Enable the `Exporters` in Wiclax. Only one exporter is needed to be configured and activated.
    1. Set with the following parameters, while leave all the other parameters to their default values:
        - `Tipo`: `TCP Server`
        - `Target endpoint`: `0.0.0.0`
        - `Port`: `1234` (or any other port, but make sure to update the `config.json` file accordingly)
        - `Format`: `Default JSON`
        - `Information`: `Passaggi recenti`
 5. Make sure the display board is correctly connected to the LAN with known IP address and port, and update the `config.json` file accordingly.
 Usually, the port is `21967` for the Microtab Led Display, but remember to check.
 6. Edit the `config.json` file to set the right IP address and port for the Microgate display and the Wiclax server connection settings.
 The IP to connect to Wiclax is the IP address of the machine where Wiclax is running, and the port is the one configured in the Exporter settings in Wiclax (e.g. `1234`).
 7. Edit the `config.json` changing the `display` settings parameters to your needs such as time thresholds for cycling through the athletes when several of them pass through the checkpoint at the same time, and the rendering settings for the display.
 8. Launch the utility and enjoy the show! `lap-counter` if installed as a package


## Wiclax codes
### Wiclax formula for the `msg` field

```python
Iif([Giri] >= 1,
Iif([Giri] % 4 = 0,
    Concat('E', Floor([Giri] / ToInt([n_laps]))),
    [Giri] % 4),
'-')
```

### For the `display` field
```python
Iif([Giri] >= 1,
   Iif([Giri] % 4 = 0,
       "True",
       "False"), 
"False")
```

Required fields in Wiclax:
- `n_laps`: numeric field to count the number of laps for each athlete, e.g. `Giri` in the example formula above.
- `id`: unique identifier for each athlete, e.g. `bib` field in Wiclax. or name
- `msg`: field to inform athlete of progress: go to exercise station, how many laps completed
- `display`: if you want to display. Critera to be defined in Wiclax

## Set the font and number of display boards logic

### Display Configuration Guide

The system determines the layout of your display by balancing the **physical hardware** (number of boards) against your **font selection**.

### 1. Font Selection
The `font` setting dictates the density of information on the screen:

* **Large Font (`0` or `2`):** Best for high visibility. Each physical board displays exactly **one** logical row of data.
* **Small Font (`1`):** Best for information density. The system maximizes the number of logical rows that can fit across your total physical height.

---

### 2. Logical Row Calculation
The number of logical rows is automatically calculated based on your `n_rows` (physical boards) and the selected font.

| Font Type | `default_font` | Calculation Logic |
| :--- | :--- | :--- |
| **Large** | `0` or `2` | $\text{Logical Rows} = n\_rows$ |
| **Small** | `1` | $\text{Logical Rows} = \frac{(n\_rows \times 17) - 1}{9}$ (rounded for even spacing) |

> **Example:** If you have **2 physical boards** and use the **Small Font**, the system will automatically generate **3 logical rows**.

---

### 3. Pagination & Scrolling
To manage how data transitions across the screen, use the pagination offset:

* **`offset_pagination`**: Defines the "jump" size. 
    * *Example:* If set to `2`, the display will skip 2 athletes when scrolling to the next page, ensuring a consistent flow of information without overlapping too much previous data.

# Available `id` transformations in Wiclax
It is possible to apply some transformations to the `id` field in Wiclax, so that the utility can display different information on the board.
Available transformations are:
- `do_not_transform`
- `pad_bib_space_4`
- `pad_bib_space_3`
- `pad_bib_zero_4`
- `pad_bib_zero_3`
- `trim_4`
- `trim_3`
- `to_lower`
- `to_upper`
- `capitalize`