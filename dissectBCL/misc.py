import os
import sys
import configparser
import xml.etree.ElementTree as ET
import glob
from dissectBCL.logger import log
import pandas as pd


# Define config reader.
def getConf():
    # Get userDir
    homeDir = os.path.expanduser("~")
    # Fetch ini file and stop when it's not there.
    confLoc = os.path.join(homeDir, 'dissectBCL.ini')
    if not os.path.exists(confLoc):
        log.critical(
            "[red]Ini file not found. (~/dissectBCL.ini) Exiting..[/red]"
        )
        sys.exit(1)
    else:
        # Read config and return
        config = configparser.ConfigParser()
        config.read(confLoc)
        return config


# Find new flowcells.
def getNewFlowCell(config):
    # set some config vars.
    baseDir = config['Dirs']['baseDir']
    outBaseDir = config['Dirs']['outputDir']
    # Glob over the bcl directory to get all flowcells.
    flowCells = glob.glob(
        os.path.join(baseDir, '*', 'RTAComplete.txt')
        )
    # Check if the flowcell exists in the output directory.
    for flowcell in flowCells:
        flowcellName = flowcell.split('/')[-2]
        flowcellDir = flowcell.replace("/RTAComplete.txt", "")
        # Look for a folder containing the flowcellname.
        # If there is no folder matching the flowcell name, start the pipeline.
        if not glob.glob(
            os.path.join(outBaseDir, flowcellName) + "*"
        ):
            return flowcellName, flowcellDir
        # If a matching folder exists, but no flag, start the pipeline:
        elif not glob.glob(
            os.path.join(outBaseDir, flowcellName + '*', 'communication.done')
        ):
            return flowcellName, flowcellDir
    return None


# Parse runInfo.xml
def parseRunInfo(runInfo):
    tree = ET.parse(runInfo)
    root = tree.getroot()
    readDic = {}
    for i in root.iter():
        if i.tag == 'Read':
            if i.attrib['IsIndexedRead'] == 'Y':
                readType = 'Index'
            else:
                readType = 'Read'
            readKey = 'Read' + i.attrib['Number']
            readDic[readKey] = [i.attrib['NumCycles'], readType]
        if i.tag == 'FlowcellLayout':
            lanes = int(i.attrib['LaneCount'])
        if i.tag == 'Instrument':
            instrument = i.text
        if i.tag == 'Flowcell':
            flowcellID = i.text
    return {
        'readDic': readDic,
        'lanes': lanes,
        'instrument': instrument,
        'flowcellID': flowcellID
    }


def hamming(s1, s2):
    # We have some basket cases (multimodal)
    # Where barcode is nan (type as float)
    # Ignore these for now.
    if type(s1) == float or type(s2) == float:
        return 0
    dist = 0
    for step in range(len(s1)):
        if s1[step] != s2[step]:
            dist += 1
    return dist


def joinLis(lis, joinStr=""):
    """
    join a list into a string (without spaces).
    elements are converted to strings.
    """
    return joinStr.join([str(i) for i in lis])


def lenMask(recipe, minl):
    """
    take length of recipe (runInfo) and length of a barcode and return a mask.
    e.g. 8bp index, 10bp sequenced, returns I8N2
    """
    if recipe-minl > 0:
        return "I{}N{}".format(minl, recipe-minl)
    else:
        return "I{}".format(minl)


def P5Seriesret(df):
    if 'index2' in list(df.columns):
        return df['index2']
    else:
        return pd.Series()


def screenFqFetcher(IDdir):
    """
    Return what fastq file should be used in the fastq screen.
    Prioritize R3 > R2 > R1
    """
    fqFiles = glob.glob(
        os.path.join(
            IDdir,
            "*fastq.gz"
        )
    )
    for substr in ["_R3.fastq.gz", "_R2.fastq.gz", "_R1.fastq.gz"]:
        hit = [s for s in fqFiles if substr in s and 'optical' not in s]
        if hit:
            log.info("screenFqFetcher returns {}".format(hit[0]))
            return hit[0]


def moveOptDup(laneFolder):
    for txt in glob.glob(
        os.path.join(
            laneFolder,
            '*',
            '*',
            '*duplicate.txt'
        )
    ):
        # Field -3 == project folder
        # escape those already in a fastqc folder (reruns)
        if 'FASTQC' not in txt:
            pathLis = txt.split('/')
            pathLis[-3] = 'FASTQC_' + pathLis[-3]
            ofile = "/".join(pathLis)
            ofile.replace('duplicate.txt', 'opticalduplicates.txt')
            os.rename(txt, ofile)


def retBCstr(ser):
    if 'index2' in list(ser.index):
        return '+'.join(
            [str(ser['index']), str(ser['index2'])]
        )
    else:
        return str(ser['index'])


def retIxtype(ser):
    if 'I7_Index_ID' in list(ser.index) and 'I5_Index_ID' in list(ser.index):
        return '+'.join(
            [str(ser['I7_Index_ID']), str(ser['I5_Index_ID'])]
        ).replace('_', r'\_')
    elif 'I7_Index_ID' in list(ser.index):
        return str(ser['I7_Index_ID']).replace('_', r'\_')
    else:
        return 'NA'


def TexformatQual(qualStr):
    texStr = r""
    qualLis = str(qualStr).split(',')
    for entry in qualLis:
        qualKey = entry.split(':')[0]
        qualVal = entry.split(':')[1]
        appStr = r'''\textbf{%(entry)s:}%(val)s, ''' % {
            'entry': qualKey,
            'val': qualVal
        }
        texStr += appStr
    return(texStr[:-2])


def TexformatDepFrac(fract):
    if fract < 0.9:
        return r'''\textcolor{red}{%(val)s}''' % {
            'val': str(fract)
        }
    else:
        return(str(fract))


def ReportDFSlicer(dfLen):
    # I guess will never be more than 10000 samples.
    slices = [[i if i == 0 else i+1, i+26] for i in range(0, 10000, 25)]
    sliceLis = []
    for slice in slices:
        if slice[1] < dfLen - 1:
            sliceLis.append(slice)
        elif slice[1] > dfLen - 1:
            sliceLis.append([slice[0], dfLen + 1])
            return(sliceLis)


def truncStr(string):
    if len(string) > 24:
        return(string[0:11] + r' ... ' + string[-10::])
    else:
        return(string)


def fetchLatestSeqDir(PIpath, seqDir):
    seqDirNum = 0
    for dir in os.listdir(PIpath):
        if seqDir in dir and dir.replace(seqDir, ''):
            seqDirNum = int(dir[-1])
    if seqDirNum == 0:
        return(os.path.join(PIpath, seqDir))
    else:
        return(os.path.join(PIpath, seqDir + str(seqDirNum)))
