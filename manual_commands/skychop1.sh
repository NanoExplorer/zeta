#!/bin/bash
bash run_apecs_command.sh configure_lab_chopper1
sleep 3
bash run_apecs_command.sh take_data
sleep 7
bash run_apecs_command.sh deconfigure_chopper1
