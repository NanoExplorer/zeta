#!/bin/bash
echo "$2" | cat "$1" - | nc -u -w 1 localhost 16255
echo "" 
