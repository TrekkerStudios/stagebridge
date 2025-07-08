# StageBridge

## Components

### stagebridge (python)
* Main backend/frontend (runs on satellite)
* osc to midi WORKING
* web based config editing WORKING
* rtp midi MIXED RESULTS
* docker CURSORY IMPLEMENTATION (works on Linux?; can't access midi devices on Mac/Win)

### fleet (python)
* Fleet controller (runs on master computer)
* web manager for all running satellites WORKING

### generator (js)
* Generates OSC mappings based on CSV input
* web ui WORKING
* intended to run in browser independently, probably gonna go cf pages

### converter (WIP)
* Correct transfer of data points, but timing is off
* File naming conventions and batch processing are all working as intended
