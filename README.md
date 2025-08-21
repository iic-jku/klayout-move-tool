# KLayout Plugin: Move Quickly Tool

<!--
[![Watch the demo](doc/klayout-move-screenshot-demo-video.gif)](https://youtube.com/watch/v=TODO)
-->
<p align="center">
<img align="middle" src="doc/klayout-move-screenshot.jpg" alt="KLayout Move Quickly Tool" width="800"/>
</p>

* Boost your layout productivity with quick moves of layout elements, such as
   * cell instances
   * shapes (e.g. polygons, boxes, paths)

This add-on can be installed through [KLayout](https://klayout.de) package manager, [see installation instructions here](#installation-instructions)

After installation, this tool can be accessed through *Toolbar*→*Move quickly*

## Usage

### Pre-selection

- You can select instances and shapes (you want to move), before invoking the tool
   - The selection will be displayed in the dock setup panel

### Tool activation and deactivation

- Click the *Move Quickly* tool or press `M` to enter the tool mode (if you've configured the key binding [as explained here](#shortcut)
- Press `Esc` at any time to abort the tool and activate the regular KLayout selection tool.

### Example 1: Moving single object (mouse)

- Activate the tool
- If there is no selection, left-click an object to move it
- Otherwise, left-click again to move it
- Move the mouse to the destination
- Click to move the object

### Example 2: Moving single object (keyboard)

- Activate the tool
- Left-click an object to select it
- Press `Tab` to enter the dock setup widget
- Provide either absolute positions or relativ deltas
- Press `Enter` to commit the move operation

### Example 3: Extend selection
- Activate the tool
- Select an object
- Hold `Shift` and select additional object(s)
- Click to start moving
- Move the mouse to the desired destination
- Commit the move operation with a click or by pressing `Enter`

### Example 4: Drag selection
- Activate the tool
- Select object(s) by dragging the mouse
- Hold `Shift` and select additional object(s)
- Click to start moving
- Move the mouse to the desired destination
- Commit the move operation with a click or by pressing `Enter`

 
## Pro-Tip: assign key binding `M` to the tool
<a id="shortcut"></a>

- In the main menu, open the Preferences/Settings in KLayout
- Navigate to *Application*→*Customize Menu*
- Search for 'Move'
- Assign the shortcut `M` to the path `edit_menu.mode_menu.Move_quickly`

<p align="center">
<img align="middle" src="doc/assign-shortcut.jpg" alt="Assign shortcut 'M' to the 'Move quickly' tool" width="800"/>
</p>

## Installation using KLayout Package Manager

<a id="installation-instructions"></a>

1. From the main menu, click *Tools*→*Manage Packages* to open the package manager
<p align="center">
<img align="middle" src="doc/klayout-package-manager-install1.jpg" alt="Step 1: Open package manager" width="800"/>
</p>

2. Locate the `MoveQuicklyToolPlugin`, double-click it to select for installation, then click *Apply*
<p align="center">
<img align="middle" src="doc/klayout-package-manager-install2.jpg" alt="Step 2: Choose and install the package" width="1200"/>
</p>

3. Review and close the package installation report
<p align="center">
<img align="middle" src="doc/klayout-package-manager-install3.jpg" alt="Step 3: Review the package installation report" width="600"/>
</p>

4. Confirm macro execution
<p align="center">
<img align="middle" src="doc/klayout-package-manager-install4.jpg" alt="Step 4: Confirm macro execution" width="500"/>
</p>

