import os
import argparse
import xml.etree.ElementTree as ET
import logging
import json
import configparser

import requests
import interop
import pandas as pd


def getConf(configfile):
    "Adapted from from dissectBCL.misc.getConf"

    config = configparser.ConfigParser()
    logging.info("Reading configfile from {}".format(configfile))
    config.read(configfile)
    return config

def pushParkour(flowcellID, bclFlowcellOutDir, config, flowcellBase):
    # pushing out the 'Run statistics in parkour'.
    '''
    we need:
     - R1 > Q30 % - done
     - R2 > Q30 % (if available) - done
     - clusterPF (%) - done
     - name (== laneStr) - done
     - undetermined_indices (%) - done
     - reads_pf (M) - can be obtained by parsing interop

    Adapted from from dissectBCL.fakeNews.pushParkour
    '''
    # Parse interop.
    iop_df = pd.DataFrame(
        interop.summary(
            interop.read(
                flowcellBase
            ),
            'Lane'
        )
    )

    FID = flowcellID
    if '-' in FID:
        FID = FID.split('-')[1]
    d = {}
    d['flowcell_id'] = FID
    laneDict = {}
    # Quality_Metrics.csv contains all the info we need.
    qdf = pd.read_csv(bclFlowcellOutDir)
    # If a flowcell is split, qMetPath contains only Lane 1 e.g.
    # If not, all lanes sit in qdf
    # Anyhow, iterating and filling will capture all we need.
    for lane in list(qdf['Lane'].unique()):
        subdf = qdf[qdf['Lane'] == lane]
        laneStr = 'Lane {}'.format(lane)
        laneDict[laneStr] = {}
        # reads PF.
        readsPF = iop_df[
            (iop_df['ReadNumber'] == 1) & (iop_df['Lane'] == lane)
        ]['Reads Pf'].values
        logging.info('lane {}, reads PF = {}'.format(lane, float(readsPF)))
        laneDict[laneStr]['reads_pf'] = float(readsPF)
        # Und indices.
        laneDict[laneStr]["undetermined_indices"] = \
            round(
                subdf[
                    subdf["SampleID"] == "Undetermined"
                ]["YieldQ30"].sum() / subdf['YieldQ30'].sum() * 100,
                2
            )
        Q30Dic = subdf.groupby("ReadNumber")['% Q30'].mean().to_dict()
        for read in Q30Dic:
            if 'I' not in str(read):
                readStr = 'read_{}'.format(read)
                laneDict[laneStr][readStr] = round(Q30Dic[read]*100, 2)
        laneDict[laneStr]["cluster_pf"] = round(
            subdf["YieldQ30"].sum()/subdf["Yield"].sum() * 100,
            2
        )
        laneDict[laneStr]["name"] = laneStr
    d['matrix'] = json.dumps(list(laneDict.values()))
    logging.info("Pushing FID with dic {} {}".format(FID, d))
    pushParkStat = requests.post(
        config.get("parkour", "pushURL"),
        auth=(
            config.get("parkour", "user"),
            config.get("parkour", "password")
        ),
        data=d,
        verify=config['parkour']['cert']
    )
    logging.info("ParkourPush return {}".format(pushParkStat))
    return pushParkStat

def parse_cmd_args():
    "Parse command-line arguments"

    cmd_arg_parser = argparse.ArgumentParser()
    cmd_arg_parser.add_argument('--configFile', required=True)
    cmd_arg_parser.add_argument('--flowcellDir', required=True)
    cmd_arg_parser.add_argument('--bclFlowcellOutDir', required=True)
    return cmd_arg_parser.parse_args()

def getFlowcellId(run_info_path):
    """
    Takes the path to runInfo.xml and parses it.
    Returns:
        - the flowcellID (str)

    Adapted from dissectBCL.classes.flowCellClass.parseRunInfo
    """
    tree = ET.parse(run_info_path)
    root = tree.getroot()
    for i in root.iter():
        if i.tag == 'Flowcell':
            flowcellID = i.text
    return flowcellID

def main(config, flowcell_dir, bcl_flowcell_out_dir):

    flowcell_id = getFlowcellId(os.path.join(flowcell_dir, 'RunInfo.xml'))

    pushParkour(flowcell_id,
                bcl_flowcell_out_dir,
                config,
                flowcell_dir)

if __name__ == '__main__':

    cmd_args = parse_cmd_args()
    config = getConf(cmd_args.configFile)

    main(config,
         cmd_args.flowcellDir,
         cmd_args.bclFlowcellOutDir)