"""
Auxiliary module with simple utility and informative functions.

Link to project repository
--------------------------
`https://github.com/pklesk/mcts_numba_cuda <https://github.com/pklesk/mcts_numba_cuda>`_
"""

import cpuinfo
import platform
import psutil
from numba import cuda
import pickle
import time
import zipfile as zf
import os
import json
import sys

__author__ = "Przemysław Klęsk"
__email__ = "pklesk@zut.edu.pl"


def dict_to_str(d, indent=0):
    """Returns a vertically formatted string representation of a dictionary."""
    indent_str = indent * " "
    dictionary_text = indent_str + "{"
    for item_index, key in enumerate(d):
        dictionary_text += "\n" + indent_str + "  " + str(key) + ": " + str(d[key]) + ("," if item_index < len(d) - 1 else "")
    dictionary_text += "\n" + indent_str + "}"
    return dictionary_text


def list_to_str(l, indent=0):
    """Returns a vertically formatted string representation of a list."""
    indent_str = indent * " "
    list_text = ""
    for item_index, element in enumerate(l):
        list_text += indent_str
        list_text += "[" if item_index == 0 else " "
        list_text += str(element) + (",\n" if item_index < len(l) - 1 else "]")
    return list_text


def pickle_objects(fname, some_list):
    """Pickles a list of objects to a binary file."""
    print(f"PICKLE OBJECTS... [to file: {fname}]")
    start_time = time.time()
    try:
        file_handle = open(fname, "wb+")
        pickle.dump(some_list, file_handle, protocol=pickle.HIGHEST_PROTOCOL)
        file_handle.close()
    except IOError:
        sys.exit("[error occurred when trying to open or pickle the file]")
    end_time = time.time()
    print(f"PICKLE OBJECTS DONE. [time: {end_time - start_time} s]")


def unpickle_objects(fname):
    """Returns an a list of objects from a binary file."""
    print(f"UNPICKLE OBJECTS... [from file: {fname}]")
    start_time = time.time()
    try:
        file_handle = open(fname, "rb")
        some_list = pickle.load(file_handle)
        file_handle.close()
    except IOError:
        sys.exit("[error occurred when trying to open or read the file]")
    end_time = time.time()
    print(f"UNPICKLE OBJECTS DONE. [time: {end_time - start_time} s]")
    return some_list


def cpu_and_system_props():
    """Returns a dictionary with properties of CPU and OS."""
    system_properties = {}
    cpu_information = cpuinfo.get_cpu_info()
    system_information = platform.uname()
    system_properties["cpu_name"] = cpu_information["brand_raw"]
    system_properties["ram_size"] = f"{psutil.virtual_memory().total / 1024**3:.1f} GB"
    system_properties["os_name"] = f"{system_information.system} {system_information.release}"
    system_properties["os_version"] = f"{system_information.version}"
    system_properties["os_machine"] = f"{system_information.machine}"
    return system_properties


def gpu_props():
    """Returns a dictionary with properties of GPU device."""
    gpu_device = cuda.get_current_device()
    gpu_properties = {}
    gpu_properties["name"] = gpu_device.name.decode("ASCII")
    gpu_properties["max_threads_per_block"] = gpu_device.MAX_THREADS_PER_BLOCK
    gpu_properties["max_block_dim_x"] = gpu_device.MAX_BLOCK_DIM_X
    gpu_properties["max_block_dim_y"] = gpu_device.MAX_BLOCK_DIM_Y
    gpu_properties["max_block_dim_z"] = gpu_device.MAX_BLOCK_DIM_Z
    gpu_properties["max_grid_dim_x"] = gpu_device.MAX_GRID_DIM_X
    gpu_properties["max_grid_dim_y"] = gpu_device.MAX_GRID_DIM_Y
    gpu_properties["max_grid_dim_z"] = gpu_device.MAX_GRID_DIM_Z
    gpu_properties["max_shared_memory_per_block"] = gpu_device.MAX_SHARED_MEMORY_PER_BLOCK
    gpu_properties["async_engine_count"] = gpu_device.ASYNC_ENGINE_COUNT
    gpu_properties["can_map_host_memory"] = gpu_device.CAN_MAP_HOST_MEMORY
    gpu_properties["multiprocessor_count"] = gpu_device.MULTIPROCESSOR_COUNT
    gpu_properties["warp_size"] = gpu_device.WARP_SIZE
    gpu_properties["unified_addressing"] = gpu_device.UNIFIED_ADDRESSING
    gpu_properties["pci_bus_id"] = gpu_device.PCI_BUS_ID
    gpu_properties["pci_device_id"] = gpu_device.PCI_DEVICE_ID
    gpu_properties["compute_capability"] = gpu_device.compute_capability
    CC_CORES_PER_SM_DICT = {
        (2, 0): 32,
        (2, 1): 48,
        (3, 0): 256,
        (3, 5): 256,
        (3, 7): 256,
        (5, 0): 128,
        (5, 2): 128,
        (6, 0): 64,
        (6, 1): 128,
        (7, 0): 64,
        (7, 5): 64,
        (8, 0): 64,
        (8, 6): 128
    }
    gpu_properties["cores_per_SM"] = CC_CORES_PER_SM_DICT.get(gpu_device.compute_capability)
    gpu_properties["cores_total"] = gpu_properties["cores_per_SM"] * gpu_device.MULTIPROCESSOR_COUNT
    return gpu_properties


def hash_function(s):
    """Returns a hash code (integer) for given string as a base 31 expansion."""
    hash_value = 0
    for character in s:
        hash_value *= 31
        hash_value += ord(character)
    return hash_value


def hash_str(params, digits):
    return str((hash_function(str(params)) & ((1 << 32) - 1)) % 10**digits).rjust(digits, "0")


class Logger:
    """Class for simultaneous logging to console and a log file (for purposes of experiments)."""
    def __init__(self, fname):
        """Constructor of ``MCTSNC`` instances."""
        self.logfile = open(fname, "a", encoding="utf-8")

    def write(self, message):
        """Writes a message to console and a log file."""
        self.logfile.write(message)
        self.logfile.flush()
        sys.__stdout__.write(message)

    def flush(self):
        """Empty function required for buffering."""
        pass


def experiment_hash_str(matchup_info, c_props, g_props, main_hs_digits=10, matchup_hs_digits=5, env_hs_digits=3):
    """Returns a hash string for an experiment, based on its settings and properties."""
    matchup_hash = hash_str(matchup_info, digits=matchup_hs_digits)
    environment_properties = {**c_props, **g_props}
    environment_hash = hash_str(environment_properties, digits=env_hs_digits)
    complete_experiment_info = {**matchup_info, **environment_properties}
    complete_experiment_hash = hash_str(complete_experiment_info, digits=main_hs_digits)
    experiment_hash = f"{complete_experiment_hash}_{matchup_hash}_{environment_hash}_[{matchup_info['ai_a_shortname']};{matchup_info['ai_b_shortname']};{matchup_info['game_name']};{matchup_info['n_games']}]"
    return experiment_hash


def save_and_zip_experiment(experiment_hs, experiment_info, folder):
    """Saves and zips .json and .log files for an experiment given its hash string and information stored in a dictionary."""
    print(f"SAVE AND ZIP EXPERIMENT... [hash string: {experiment_hs}]")
    start_time = time.time()
    experiment_path = folder + experiment_hs
    try:
        file_handle = open(experiment_path + ".json", "w+")
        json.dump(experiment_info, file_handle, indent=2)
        file_handle.close()
        with zf.ZipFile(experiment_path + ".zip", mode="w", compression=zf.ZIP_DEFLATED) as archive:
            archive.write(experiment_path + ".json", arcname=experiment_hs + ".json")
            archive.write(experiment_path + ".log", arcname=experiment_hs + ".log")
        os.remove(experiment_path + ".json")
        os.remove(experiment_path + ".log")
    except IOError:
        sys.exit(f"[error occurred when trying to save and zip experiment info: {fname}]")
    end_time = time.time()
    print(f"SAVE AND ZIP EXPERIMENT DONE. [time: {end_time - start_time} s]")


def unzip_and_load_experiment(experiment_hs, folder):
    """Unzips, loads an experiment given its hash string, and returns a dictionary with experiments' information."""
    print(f"UNZIP AND LOAD EXPERIMENT... [hash string: {experiment_hs}]")
    start_time = time.time()
    experiment_path = folder + experiment_hs
    try:
        with zf.ZipFile(experiment_path + ".zip", "r") as zip_archive:
            zip_archive.extract(experiment_hs + ".json", path=os.path.dirname(experiment_path + ".json"))
        with open(experiment_path + ".json", 'r', encoding="utf-8") as json_file:
            experiment_info = json.load(json_file)
        os.remove(experiment_path + ".json")
    except IOError:
        sys.exit(f"[error occurred when trying to unzip and load experiment info: {experiment_hs}]")
    end_time = time.time()
    print(f"UNZIP AND LOAD EXPERIMENT DONE. [time: {end_time - start_time} s]")
    return experiment_info
