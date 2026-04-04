# `lap-counter` utility

>This utility is 99% AI generated, designed with Google Antigravity.
>The remaining 1% is the knowledge of the author of this utility and this README file.

## Purpose

The purpose of this utility is to listen to Wiclax passing events (when athletes pass through a checkpoint triggering a signal a.k.a. lap) and displaying it to the Microgate display.

It is specifically tailored to suit the needs to time the Hybrid Race format, where athletes lap 4 times a course, do an additional task (e.g. dumbbell lifts, ...) and then repeat the process until they have completed a total of 8 tasks.

It is designed to work with the `Alfa` protocol and was tested on the **Microtab Led Display** using .netBoards.

When several athletes pass through the checkpoint at the same time, the utility will cycle through the athletes' bib numbers and associated msg (computed on Wiclax) on the display board, showing each name for a short period of time.
The time threshold for cycling through the athletes can be configured in the `config.json` file.

Make sure to configure the right IP address and port for the Microgate display in the `config.json` file and the Wiclax server connection settings as well.

There is no need to interact with the utility directly, as it will automatically listen to the Wiclax events and update the display accordingly.

Some diagnostic logs are printed to the console for debugging purposes, but they can be ignored during normal operation.

## Installation

### From git via pip

`pip install git+https://github.com/tommaso-bertola/lap-counter.git@main`

Upgrade when new versions are released:
`pip install --upgrade git+https://github.com/tommaso-bertola/lap-counter.git@main`

### Run from source

From the project root:

`python listen.py`

### Install as a package

From the project root:

`pip install .`

Then run:

`lap-counter`

## Configuration file location and priority

The app now supports packaged execution with a user-writable config file.

At startup, configuration is resolved in this order:

1. `LAP_COUNTER_CONFIG` environment variable (absolute path recommended)
2. local `config.json` in the current working directory
3. OS user config path (auto-created from packaged defaults if missing)

### macOS path

When installed as a package on macOS, edit this file:

`~/Library/Application Support/lap-counter/config.json`

If it does not exist, the app creates it automatically on first run using the bundled default configuration.

### Example override

`LAP_COUNTER_CONFIG=/absolute/path/to/config.json lap-counter`

## Usage task list

 1. Open Wiclax and create the additional fields required to send the info to the utility.
 Remember to click `Apply` before creating the new fields, otherwise Wiclax will not be able to recognize the new fields in the formula editor.
    1. Create a `n_laps` field to count the number of laps for each athlete. This can vary based on the track length and race format specifics. For the Hybrid Race format, it should be set to 4 laps on a 200m track.
    Make sure it is a **numeric** field and available in the Results view.
    2. Create a `msg` field to compute the message to be displayed on the Microgate display. The forumla is as follows, but can be adapted to any visualization need.
    Make sure it is available in the Results view.
 2. Enable the `Live` mode in Wiclax.
 3. Enable the `Exporters` in Wiclax. Only one exporter is needed to be configured and activated.
    1. Set with the following parameters, while leave all the other parameters to their default values:
        - `Tipo`: `TCP Server`
        - `Target endpoint`: `0.0.0.0`
        - `Port`: `4242` (or any other port, but make sure to update the `config.json` file accordingly)
        - `Format`: `Default JSON`
        - `Information`: `Passaggi recenti`
 4. Make sure the display board is correctly connected to the LAN with known IP address and port, and update the `config.json` file accordingly.
 Usually, the port is `29672` for the Microtab Led Display, but remember to check.
 5. Edit the `config.json` file to set the right IP address and port for the Microgate display and the Wiclax server connection settings.
 6. Edit the `config.json` changing the `display.settings` parameters to your needs.
 7. Launch the utility and enjoy the show! `python listen.py` (or `lap-counter` if installed as a package)


As you can see in `config.json`, it is possible to customize the display settings, such as the position of the text and some basic transforms to the text (e.g. uppercase, lowercase, ...). The utility will apply the transforms to the text before sending it to the display.

```python
Iif([Giri] >= 1,
Iif([Giri] % 4 = 0,
    Concat('EX', Floor([Giri] / ToInt([n_laps]))),
    Concat([Giri] % 4, '/', [n_laps])),
'-')
```

