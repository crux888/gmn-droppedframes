"""
Python script to check CapturedFiles for dropped frames, ie. FF files
with a time gap of more than {DROPPED_FRAME_TDELTA} seconds.

Dropped frames typically occur when the Raspberry Pi overheats during
capture and its CPU is throttled. They can also occur due to power cuts.

This script can be run automatically each night as an RMS external script
(see the rmsExternal function for more details). It can also be run manually
from the command line (see the commandLine function for more details).

UK0034 edit
UK0035 edit
"""


import os
import sys
import glob
import shutil
import configparser
import logging
from statistics import mean
from datetime import datetime, timedelta

import RMS.ConfigReader as cr
from PIL import Image, ImageFont, ImageDraw
from importlib import import_module as impmod
from RMS.Logger import initLogging

sys.path.append(os.path.split(os.path.abspath(__file__))[0])


# Set DROPPED_FRAME_TDELTA to the number of seconds that you
# consider to be a dropped frame.
DROPPED_FRAME_TDELTA = timedelta(seconds=15)

# Set ANNOTATE_IMAGE to True if you want the captured stack image
# to be automatically updated with the number of dropped frames.
ANNOTATE_IMAGE = True


def rmsExternal(cap_dir, arch_dir, config):
    """
    Function called when droppedFrames.py is run as an RMS external script,
    eg. from RMS_config or ukmonPostProc. Checks the latest CapturedFiles
    directory for dropped frames, ie. FF files with a time gap of more
    than {DROPPED_FRAME_TDELTA} seconds.

    If you want to trigger another Python script after this one (eg. iStream),
    create a file 'extrascript' containing the full path to the extra script.
    The extra script will be passed the same arguments as this one (cap_dir,
    arc_dir, config).
    """

    # Create rebootlockfile (to stop Pi rebooting in the middle of script)
    rebootlockfile = os.path.join(config.data_dir, config.reboot_lock_file)
    with open(rebootlockfile, 'w') as f:
        f.write('1')

    # Clear existing log handlers and set new ones for this script
    log = logging.getLogger("logger")
    while len(log.handlers) > 0:
        log.removeHandler(log.handlers[0])
    initLogging(config, 'droppedframes_')
    log.info('starting external script for dropped frames')

    # Configure system path, etc
    log.info('reading local config')
    srcdir = os.path.split(os.path.abspath(__file__))[0]
    localcfg = configparser.ConfigParser()
    localcfg.read(os.path.join(srcdir, 'config.ini'))
    sys.path.append(srcdir)

    # Check captured directory for dropped frames
    log.info('checking for dropped frames')
    results = checkDroppedFrames(cap_dir)
    log.info('analysed %i FF files', results["files analysed"])
    if results["files ignored"] != 0:
        log.info('ignored %i FF files (bad filename format)',
                 results["files ignored"])
    if results["dropped frames"] == 0:
        log.info('no dropped frames detected')
    else:
        log.info('found %i FF files with a time gap of more than %s seconds:',
                 results["dropped frames"], str(DROPPED_FRAME_TDELTA.seconds))
        for detail in results["dropped details"]:
            log.info('    %s', detail)
    if ANNOTATE_IMAGE:
        log.info('annotating images')
        for directory in [cap_dir, arch_dir]:
            files = glob.glob(
                directory + '/' + os.path.basename(directory) + '_stack*meteors.jpg')
            for original_file in files:
                # TODO: After testing, remove code that copies original image
                # ie. just make the annotation on the original image
                new_file = original_file.replace('.jpg', '_copy.jpg')
                shutil.copy(original_file, new_file)
                if results["dropped frames"] == 0:
                    message = 'No dropped frames detected'
                else:
                    if results["dropped frames"] == 1:
                        inner_msg = ' detected ('
                    else:
                        inner_msg = 's detected (average '
                    message = (f'{results["dropped frames"]} dropped frame{inner_msg}'
                               f'{results["dropped average"]} seconds)')
                annotateImage(new_file, message)
                log.info('annotated image: %s', new_file)
    log.info('finishing external script for dropped frames')

    # Test for additional script
    log.info('about to test for extra script')
    try:
        with open(os.path.join(srcdir, 'extrascript'), 'r') as extraf:
            extrascript = extraf.readline().strip()
        log.info('running additional script {:s}'.format(extrascript))
        sloc, sname = os.path.split(extrascript)
        sys.path.append(sloc)
        scrname, _ = os.path.splitext(sname)
        nextscr = impmod(scrname)
        nextscr.rmsExternal(cap_dir, arch_dir, config)
    except (IOError, OSError):
        log.info('additional script not called')
        try:
            os.remove(rebootlockfile)
        except:
            log.info('unable to remove reboot lock file, pi will not reboot')
            pass

    return


def annotateImage(img_path, message):
    """Function to annoate an image with the number of dropped frames."""
    my_image = Image.open(img_path)
    width, height = my_image.size
    image_editable = ImageDraw.Draw(my_image)
    fntheight = 20
    try:
        fnt = ImageFont.truetype("arial.ttf", fntheight)
    except:
        fnt = ImageFont.truetype("DejaVuSans.ttf", fntheight)
    # fnt = ImageFont.load_default()
    width_text, _ = image_editable.textsize(message, fnt)
    offset_x, _ = fnt.getoffset(message)
    width_text += offset_x
    top_left_x = width / 2 - width_text / 2
    image_editable.text((top_left_x, height-fntheight-15),
                        message, font=fnt, fill=(255))
    my_image.save(img_path)


def commandLine():
    """
    Function called when droppedFrames.py is run from the command line.
    Checks '/home/pi/RMS_data/CapturedFiles' for dropped frames, ie. FF
    files with a time gap of more than {DROPPED_FRAME_TDELTA} seconds.
    """

    # Initialise constants/variables
    path = '/home/pi/RMS_data/CapturedFiles'
    # path = '/Users/david/UK9999/CapturedFiles'
    total_files = 0

    # Loop through all directories in the given path
    for directory, _, _ in sorted(os.walk(path)):

        # Check directory for dropped frames
        results = checkDroppedFrames(directory)

        # Print results for current directory
        if results["files analysed"] > 0:
            print()
            print(directory)
            print(
                f'{results["files analysed"]:9,} FF files analysed.', end='')
            if results["files ignored"] == 0 and results["dropped frames"] == 0:
                print(' No dropped frames detected.')
            else:
                print()
                if results["files ignored"] > 0:
                    print(
                        f'{results["files ignored"]:9,} FF files ignored'
                        f' (bad filename format).')
                if results["dropped frames"] >= 0:
                    print(
                        f'{results["dropped frames"]:9,} FF files found with a time gap'
                        f' of more than {str(DROPPED_FRAME_TDELTA.seconds)} seconds:')
                    for detail in results["dropped details"]:
                        print(f'            {detail}')
            total_files += results["files analysed"]

    # Finish
    if total_files == 0:
        print()
        print(f'No FF files found in {path}')
    print()


def checkDroppedFrames(directory):
    """
    Function to check a directory for dropped frames, ie. FF files with
    a time gap of more than {DROPPED_FRAME_TDELTA} seconds.
    """

    # Initialise variables
    files_analysed = 0
    files_ignored = 0
    dropped_frames = 0
    dropped_times = []
    dropped_average = 0
    dropped_details = []
    previous_dt = None
    tdelta = timedelta(seconds=0)

    # Loop through all FF files
    for file in sorted(glob.glob(directory + '/*.fits')):
        fname = os.path.basename(file)
        try:
            # Extract datetime from FF filename
            current_dt = datetime.strptime(fname[10:25], '%Y%m%d_%H%M%S')
        except ValueError:
            # Unrecognised FF filename format
            files_ignored += 1
            continue

        # Check timedelta from previous FF file
        if previous_dt:
            tdelta = current_dt - previous_dt
            if tdelta > DROPPED_FRAME_TDELTA:
                dropped_frames += 1
                dropped_times.append(tdelta.seconds)
                dropped_details.append(
                    previous_dt.strftime('%d-%b-%Y %H:%M:%S') + ' → ' +
                    current_dt.strftime('%d-%b-%Y %H:%M:%S') + ' = ' +
                    str(tdelta.seconds) + ' seconds')

        # Update working variables
        files_analysed += 1
        previous_dt = current_dt

    # Calculate average duration of dropped frames
    if dropped_frames != 0:
        dropped_average = int(mean(dropped_times))

    # Return results
    return {'files analysed': files_analysed,
            'files ignored': files_ignored,
            'dropped frames': dropped_frames,
            'dropped average': dropped_average,
            'dropped details': dropped_details}


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'rmsExternal':
        # Code for testing rmsExternal function
        cap_dir = os.path.join(
            '/home/pi/RMS_data/CapturedFiles/', sys.argv[2])
        arch_dir = os.path.join(
            '/home/pi/RMS_data/ArchivedFiles/', sys.argv[2])
        config = cr.parse(".config")
        rmsExternal(cap_dir, arch_dir, config)
    else:
        # Default command line behaviour
        commandLine()
