# StageBridge

needed this for my band's live show control, most of it is vibe-coded, pr's welcome 🤙

## Versions
./bin has the old stable version but it's missing some functions
gh actions build has latest features but is not guaranteed to be stable

## Components

### stagebridge (python)
* runs on both master computer and satellites
* osc to midi WORKING
* web based config editing WORKING
* rtp midi MIXED RESULTS
* fleet manager WORKING (uses zeroconf to register all devices on network)
* osc relay WORKING
    * relays osc messages that don't match midi commands
        * relay to other registered devices
        * relay to local broadcast addr

## Extras

### generator (js)
* Generates OSC mappings based on CSV input
* web ui WORKING
* intended to run in browser independently, probably gonna go cf pages

### converter (python, heavily WIP)
* Correct transfer of data points, but timing is off
* File naming conventions and batch processing are all working as intended
