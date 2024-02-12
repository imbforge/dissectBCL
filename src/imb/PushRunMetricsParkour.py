from dissectBCL.fakeNews import pushParkour
from dissectBCL.misc import getConf
import os
import argparse
import xml.etree.ElementTree as ET


class CustomSampleSheetClass(object):

    """A very stripped-down version of 
    dissectBCL.classes.sampleSheetClass"""

    def __init__(self, lanes, flowcell):

        self.runInfoLanes = lanes
        self.flowcell = flowcell
        self.ssDic = self.parseSS()

    def parseSS(self):

        """ssDic is all we need to push to Parkour """

        ssDic = {}

        laneLis = [str(lane) for lane in range(1, self.runInfoLanes + 1, 1)]
        laneStr = self.flowcell + '_lanes_' + '_'.join(laneLis)
        ssDic[laneStr] = {'sampleSheet': None, 'lane': 'all'}

        # or
        # for lane in range(1, self.runInfoLanes + 1, 1):
        #     key = self.flowcell + '_lanes_' + str(lane)
        #     ssDic[key] = {'sampleSheet': None, 'lane': lane}

        return ssDic

def parse_cmd_args():
    "Parse command-line arguments"

    cmd_arg_parser = argparse.ArgumentParser()
    cmd_arg_parser.add_argument('--configFile', required=True)
    cmd_arg_parser.add_argument('--flowcellDir', required=True) # This should be the path to the fc dir, should contain an underscore and contain RTAComplete.txt, check
    return cmd_arg_parser.parse_args()

def parseRunInfo(runInfo):
    """
    Takes the path to runInfo.xml and parses it.
    Returns:
        - number of lanes (int)
        - the flowcellID (str)

    Adapted from dissectBCL.classes.flowCellClass
    """
    tree = ET.parse(runInfo)
    root = tree.getroot()
    for i in root.iter():
        if i.tag == 'FlowcellLayout':
            lanes = int(i.attrib['LaneCount'])
        if i.tag == 'Flowcell':
            flowcellID = i.text
    return lanes, flowcellID

def main(config, flowcell_dir):

    run_info_path = os.path.join(flowcell_dir, 'RunInfo.xml'),
    flowcell_id, flowcell_lanes = parseRunInfo(run_info_path)
    flowcell_name = flowcell_dir.split('/')[-1] # Check this, should contain an underscore and a letter identifying the sequencer after that

    sampleSheet = CustomSampleSheetClass(
        flowcell_lanes,
        flowcell_name
    )

    pushParkour(
        flowcell_id,
        sampleSheet,
        config, # Needs a meaningful config['Dirs']['outputDir'] to look for lane-specific Quality_Metrics.csv
        flowcell_dir
    )

if __name__ == '__main__':

    cmd_args = parse_cmd_args()
    config = getConf(cmd_args.configFile, True)
    flowcell_dir = cmd_args.flowcellDir

    main(config, flowcell_dir)