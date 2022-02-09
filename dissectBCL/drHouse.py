from dissectBCL.classes import drHouseClass
import pandas as pd
import os
import shutil
import glob
import datetime
import re


def getDiskSpace(outputDir):
    total, used, free = shutil.disk_usage(outputDir)
    return(total // (2**30), free // (2**30))


def matchOptdupsReqs(optDups, ssdf):
    _optDups = []
    for lis in optDups:
        sample = lis[1]
        req = ssdf[
            ssdf['Sample_Name'] == sample
        ]['reqDepth'].values
        got = ssdf[
            ssdf['Sample_Name'] == sample
        ]['gotDepth'].values
        reqvgot = float(got/req)
        _optDups.append(
            [lis[0], sample, lis[2], round(reqvgot, 2)]
        )
    return(_optDups)


def initClass(outPath, initTime, flowcellID, ssDic, transferTime, shipDic):
    ssdf = ssDic['sampleSheet']
    barcodeMask = ssDic['mask']
    mismatch = " ".join(
        [i + ': ' + str(j) for i, j in ssDic['mismatch'].items()]
    )
    # Get undetermined
    muxPath = os.path.join(
        outPath,
        'Reports',
        'Demultiplex_Stats.csv'
    )
    muxDF = pd.read_csv(muxPath)
    totalReads = int(muxDF['# Reads'].sum())
    if len(muxDF[muxDF['SampleID'] == 'Undetermined']) == 1:
        undReads = int(muxDF[muxDF['SampleID'] == 'Undetermined']['# Reads'])
    else:
        undDic = dict(
            muxDF[
                muxDF['SampleID'] == 'Undetermined'
            ][['Lane', '# Reads']].values
        )
        undStr = ""
        for lane in undDic:
            undStr += "Lane {}: {}%, ".format(
                lane,
                round(100*undDic[lane]/totalReads, 2)
            )
            undReads = undStr[:-1]
    # topBarcodes
    BCPath = os.path.join(
        outPath,
        'Reports',
        'Top_Unknown_Barcodes.csv'
    )
    bcDF = pd.read_csv(BCPath)
    bcDF = bcDF.head(5)
    BCs = [
        '+'.join(list(x)) for x in bcDF.filter(like='index', axis=1).values
    ]
    BCReads = list(bcDF['# Reads'])
    BCDic = dict(zip(
        BCs, BCReads
    ))
    # runTime
    runTime = datetime.datetime.now() - initTime
    # optDups
    optDups = []
    for opt in glob.glob(
        os.path.join(
            outPath,
            '*/*/*duplicate.txt'
        )
    ):
        project = opt.split('/')[-3].replace("FASTQC_", "")
        sample = opt.split('/')[-1].replace(".duplicate.txt", "")
        with open(opt) as f:
            dups = f.read()
            dups = dups.strip().split()
            if float(dups[1]) != 0:
                optDups.append(
                    [
                        project,
                        sample,
                        round(100*float(dups[0])/float(dups[1]), 2)
                    ]
                )
            else:
                optDups.append(
                    [
                        project,
                        sample,
                        "NA"
                    ]
                )
    projSamDic = pd.Series(
        ssdf['Sample_Project'].values,
        index=ssdf['Sample_Name']
    ).to_dict()
    for sample in projSamDic:
        if not any(sample in sl for sl in optDups):
            optDups.append(
                [
                    projSamDic[sample],
                    sample,
                    'NA'
                ]
            )
    optDups = matchOptdupsReqs(optDups, ssdf)
    # Fetch organism and fastqScreen
    sampleDiv = {}
    for screen in glob.glob(
        os.path.join(
            outPath,
            '*/*/*screen.txt'
        )
    ):
        screenDF = pd.read_csv(
            screen, sep='\t', skip_blank_lines=True, header=0, skiprows=[0]
        )
        screenDF = screenDF.dropna()
        sample = re.sub('_R[123]_screen.txt', '', screen.split('/')[-1])
        # Simpson diversity.
        # we use the D = sum( (n/N)^2 ) with n=speciescount, N=populationcount
        if not screenDF['#One_hit_one_genome'].sum() == 0:
            N = screenDF['#One_hit_one_genome'].sum()
            simpson = sum(
                [
                    (n/N)**2 for n in list(screenDF['#One_hit_one_genome'])
                ]
            )
            sampleDiv[sample] = round(simpson, 2)
        else:
            sampleDiv[sample] = 'NA'
    return(drHouseClass(
        undetermined=undReads,
        totalReads=totalReads,
        topBarcodes=BCDic,
        spaceFree=getDiskSpace(outPath),
        runTime=runTime,
        optDup=optDups,
        flowcellID=flowcellID,
        outLane=outPath.split('/')[-1],
        simpson=sampleDiv,
        mismatch=mismatch,
        barcodeMask=barcodeMask,
        transferTime=transferTime,
        shipDic=shipDic
    ))
