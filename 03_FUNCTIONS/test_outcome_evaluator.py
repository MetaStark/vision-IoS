#!/usr/bin/env python3
"""Test outcome evaluator"""
import os

print("Script location:", os.path.abspath(__file__))
print("Log file location:", os.path.join(os.path.dirname(__file__), 'dir_016_outcome_evaluator.log'))
print("File exists:", os.path.exists(os.path.join(os.path.dirname(__file__), 'dir_016_outcome_evaluator.log')))
