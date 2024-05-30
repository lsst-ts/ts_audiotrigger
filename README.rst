###################
ts_audio_trigger
###################

Code for handling enclosure monitoring for the TunableLaser.
This code is expected to run on a Raspberry Pi that has a microphone (USB) and relay switch to the TunableLaser interlock(GPIO) attached to it.

    generate_pre_commit_conf --no-mypy # Generate the pre-commit config file as well as download the configuration files.
    pre-commit install # Run the hooks at commit time and only on files modified
    pre-commit run --all # Check if the hooks are installed correctly and are working
