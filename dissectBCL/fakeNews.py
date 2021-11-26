import requests
import logging
import pandas as pd

# Set up the logger. This is used over all the modules in the package.
log = logging.getLogger()


# Definitions.
def setLog(logFile):
    logging.basicConfig(
        filename = logFile,
        level="DEBUG",
        format="%(levelname)s    %(asctime)s    %(message)s",
        filemode = 'w'
    )
    log = logging.getLogger()

def pullParkour(flowcellID, config):
    """
    Look for the flowcell/lane in parkour for the library type.
    The flowcell ID is of form:
     - 210608_A00931_0309_BHCCMWDRXY
     - 211105_M01358_0001_000000000-JTYPH
    we need "HCCMWDRXY" or "JTYPH" for the request.
    what specifies what URL to use (from config). Can be:
     - pullURL
     - pullDepthURL (to fetch requested depths)
     - pullIxURL (to fetch index types [mainly used to identify NUGen ovation solo libs].)
    """
    FID = flowcellID.split('_')[3][1::]
    if '-' in FID:
        FID = FID.split('-')[1]
    log.info("Pulling parkour for with flowcell {} using FID {}".format(flowcellID, FID))
    d = {'flowcell_id': FID}
    res = requests.get(config['parkour']['pullURL'], auth=(config['parkour']['user'], config['parkour']['password']), params=d)
    if res.status_code == 200:
        log.info("parkour API code 200")
        # res.json() returns a nested dict:
        # {project:{sampleID:[name, libType, protocol, genome, indextype, depth]}}
        # Flatten this out to a nested list so we can output a pandas dataframe.
        flatLis = []
        for project in res.json():
            for sample in res.json()[project]:
                flatLis.append([project, sample] + res.json()[project][sample])
        parkourDF = pd.DataFrame(flatLis)
        parkourDF.columns = [
                'Sample_Project',
                'Sample_ID',
                'Sample_Name',
                'Library_Type',
                'Description',
                'Organism',
                'indexType',
                'reqDepth'
            ]
        return parkourDF
    log.warning("parkour API not 200!")
    return pd.DataFrame()
