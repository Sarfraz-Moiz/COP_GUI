@echo off
cd /d "%~dp0.."
call conda activate copSim
python scripts\simulation_gui.py
