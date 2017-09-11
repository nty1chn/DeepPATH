'''
    File name: nc
    Modified by: Nicolas Coudray
    Date created: March/2017
    Python Version: 2.7 (native on the cluster)

        Objective:
        Starting with tiles images, select images from a given magnification and order them according the the stage of the cancer, or type of cancer, etc...

        Usage:
                SourceFolder is the folder where all the svs images have been tiled . :
                It encloses:
                  * 1 subfolder per image, (the name of the subfolder being "imagename_files")
                  * each contains 14-17 subfolders which name is the magnification of the tiles and contains the tiles
                It should not enclose any other folder
                The output folder from which the script is run should be empty

'''
import json
from glob import glob
import os
from argparse import ArgumentParser
import random


def extract_stage(metadata):
    stage = metadata['cases'][0]['diagnoses'][0]['tumor_stage']
    stage = stage.replace(" ", "_")
    stage = stage.rstrip("a")
    stage = stage.rstrip("b")
    return stage


def extract_cancer(metadata):
    return metadata['cases'][0]['project']['project_id']


def extract_sample_type(metadata):
    return metadata['cases'][0]['samples'][0]['sample_type']


def sort_cancer_stage_separately(metadata, **kwargs):
    sample_type = extract_sample_type(metadata)
    cancer = extract_cancer(metadata)
    if "Normal" in sample_type:
        stage = sample_type.replace(" ", "_")
    else:
        stage = extract_stage(metadata)

    return os.path.join(cancer, stage)


def sort_cancer_stage(metadata, **kwargs):
    sample_type = extract_sample_type(metadata)
    cancer = extract_cancer(metadata)
    stage = extract_stage(metadata)
    if "Normal" in sample_type:
        return sample_type.replace(" ", "_")
    return cancer + "_" + stage


def sort_type(metadata, **kwargs):
    cancer = extract_cancer(metadata)
    sample_type = extract_sample_type(metadata)
    if "Normal" in sample_type:
        return sample_type.replace(" ", "_")
    return cancer


def sort_cancer_type(metadata, **kwargs):
    sample_type = extract_sample_type(metadata)
    if "Normal" in sample_type:
        return None
    return extract_cancer(metadata)


def sort_cancer_healthy_pairs(metadata, **kwargs):
    sample_type = extract_sample_type(metadata)
    cancer = extract_cancer(metadata)
    if "Normal" in sample_type:
        return os.path.join(cancer, sample_type.replace(" ", "_"))
    return os.path.join(cancer, cancer)


def sort_cancer_healthy(metadata, **kwargs):
    sample_type = extract_sample_type(metadata)
    cancer = extract_cancer(metadata)
    if "Normal" in sample_type:
        return sample_type.replace(" ", "_")
    return cancer


def sort_random(metadata, **kwargs):
    AllOptions = ['TCGA-LUAD', 'TCGA-LUSC', 'Solid_Tissue_Normal']
    return AllOptions[random.randint(0, 2)]


def sort_mutational_burden(metadata, load_dic, **kwargs):
    submitter_id = metadata["cases"][0]["submitter_id"]
    try:
        return load_dic[submitter_id]
    except KeyError:
        return None


sort_options = [
        sort_cancer_stage_separately,
        sort_cancer_stage,
        sort_type,
        sort_cancer_type,
        sort_cancer_healthy_pairs,
        sort_cancer_healthy,
        sort_random,
        sort_mutational_burden
]

if __name__ == '__main__':
    descr = """
    Example: python 0d_SortTiles_stage.py '/ifs/home/coudrn01/NN/Lung/Test_All512pxTiled/512pxTiled' '/ifs/home/coudrn01/NN/Lung/RawImages/metadata.cart.2017-03-02T00_36_30.276824.json' 20 5 3 15 15

    The images are expected to be in folders in this directory: '/ifs/home/coudrn01/NN/Lung/Test_All512pxTiled/512pxTiled'
    Each images should have its own folder with the svs image name followed by '_files'
    Each images should have subfolders with names corresponding to the magnification associated with the jpeg tiles saved inside it
    The sorting will be done using tiles corresponding to a magnification of 20 (+/- 5 if the 20 folder does not exist)
    15%% will be put for validation, 15%% for testing and the leftover for training
    linked images' names will start with 'train_', 'test_' or 'valid_' followed by the svs name and the tile ID
    Sorting options are:
        1. sort according to cancer stage (i, ii, iii or iv) for each cancer separately (classification can be done separately for each cancer)
        2. sort according to cancer stage (i, ii, iii or iv) for each cancer  (classification can be done on everything at once)
        3. sort according to type of cancer (LUSC, LUAD, or Nomal Tissue)
        4. sort according to type of cancer (LUSC, LUAD)
        5. sort according to type of cancer / Normal Tissue (2 variables per type)
        6. sort according to cancer / Normal Tissue (2 variables)
        7. Random labels (3 variables for false positive control)
        8. sort according to mutational load (High/Low). Must specify --TMB option.
    """
    ## Define Arguments
    parser = ArgumentParser(description=descr)
    parser.add_argument("SourceFolder", help="path to tiled images")
    parser.add_argument("JsonFile", help="path to metadata json file")
    parser.add_argument("Magnification", help="magnification to use", type=float)
    parser.add_argument("MagDiffAllowed", help="difference allwed on Magnification", type=float)
    parser.add_argument("SortingOption", help="see option at the epilog", type=int)
    parser.add_argument("PercentValid", help="percentage of images for validation (between 0 and 100)", type=float)
    parser.add_argument("PercentTest", help="percentage of images for testing (between 0 and 100)", type=float)
    parser.add_argument("--TMB", help="path to json file with mutational loads")

    ## Parse Arguments
    args = parser.parse_args()

    SourceFolder = os.path.abspath(args.SourceFolder)
    imgFolders = glob(os.path.join(SourceFolder, "*_files"))
    random.shuffle(imgFolders)  # randomize order of images

    JsonFile = args.JsonFile
    with open(JsonFile) as fid:
        jdata = json.loads(fid.read())
    jdata = dict((jd['file_name'].rstrip('.svs'), jd) for jd in jdata)

    Magnification = args.Magnification
    MagDiffAllowed = args.MagDiffAllowed

    SortingOption = args.SortingOption - 1  # transform to 0-based index
    try:
        sort_function = sort_options[SortingOption]
    except IndexError:
        raise ValueError("Uknown sort option")

    PercentValid = args.PercentValid / 100.
    if not 0 < PercentValid < 1:
        raise ValueError("PercentValid is not between 0 and 100")
    PercentTest = args.PercentTest / 100.
    if not 0 < PercentTest < 1:
        raise ValueError("PercentTest is not between 0 and 100")
    # Tumor mutational burden dictionary
    TMBFile = args.TMB
    mut_load = {}
    if TMBFile:
        with open(TMBFile) as fid:
            mut_load = json.loads(fid.read())
    elif SortingOption == 7:
        raise ValueError("For SortingOption = 8 you must specify the --TMB option")

    ## Main Loop
    print("******************")
    Classes = {}
    for cFolderName in imgFolders:
        print("**************** starting %s" % cFolderName)
        imgRootName = os.path.basename(cFolderName)
        imgRootName = imgRootName.rstrip('_files')

        try:
            image_meta = jdata[imgRootName]
        except KeyError:
            print("file_name not found in metadata")
            continue

        SubDir = sort_function(image_meta, load_dic=mut_load)
        if SubDir is None:
            print("image not valid for this sorting option")
            continue
        if not os.path.exists(SubDir):
            os.makedirs(SubDir)

        try:
            Classes[SubDir].append(imgRootName)
        except KeyError:
            Classes[SubDir] = [imgRootName]

        # Check in the reference directories if there is a set of tiles at the desired magnification
        AvailMagsDir = [x for x in os.listdir(cFolderName)
                        if os.path.isdir(os.path.join(cFolderName, x))]
        AvailMags = tuple(float(x) for x in AvailMagsDir)
        # check if the mag was known for that slide
        if max(AvailMags) < 0:
            print("Magnification was not known for that file.")
            continue
        mismatch, imin = min((abs(x - Magnification), i) for i, x in enumerate(AvailMags))
        if mismatch <= MagDiffAllowed:
            AvailMagsDir = AvailMagsDir[imin]
        else:
            # No Tiles at the mag within the allowed range
            print("No Tiles found at the mag within the allowed range.")
            continue

        # Copy/symbolic link the images into the appropriate folder-type
        print("Symlinking tiles...")
        SourceImageDir = os.path.join(cFolderName, AvailMagsDir, "*")
        AllTiles = glob(SourceImageDir)
        for TilePath in AllTiles:
            TileName = os.path.basename(TilePath)
            NewImageDir = os.path.join(SubDir, "_".join(("train", imgRootName, TileName)))  # all train initially
            os.symlink(TilePath, NewImageDir)

    # Partition the dataset into train / test / valid
    print("********* Partitioning files to train / test / valid")
    for SubDir, Images in Classes.items():
        print("Working in Class %s" % SubDir)
        Nimages = len(Images)
        Ntest = int(round(Nimages * PercentTest))
        Nvalid = int(round(Nimages * PercentValid))
        print("Total number of images %d" % Nimages)
        print("Number of test images %d" % Ntest)
        print("Number of validation images %d" % Nvalid)
        # rename first <Nvalid> images
        NbTilesValid = 0
        for imgRootName in Images[:Nvalid]:
            oldprefix = "train_" + imgRootName
            newprefix = "valid_" + imgRootName
            TileGlob = os.path.join(SubDir, oldprefix + "_*")
            for TilePath in glob(TileGlob):
                os.rename(TilePath, TilePath.replace(oldprefix, newprefix))
                NbTilesValid += 1
        # rename last <Ntest> images
        NbTilesTest = 0
        for imgRootName in Images[-Ntest:]:
            oldprefix = "train_" + imgRootName
            newprefix = "test_" + imgRootName
            TileGlob = os.path.join(SubDir, oldprefix + "_*")
            for TilePath in glob(TileGlob):
                os.rename(TilePath, TilePath.replace(oldprefix, newprefix))
                NbTilesTest += 1

        NbTiles = len(os.listdir(SubDir))
        NbTilesTrain = NbTiles - NbTilesTest - NbTilesValid
        pTrain = 100.0 * NbTilesTrain / NbTiles
        pValid = 100.0 * NbTilesValid / NbTiles
        pTest  = 100.0 * NbTilesTest  / NbTiles
        print("Done. %d tiles linked to %s " % (NbTiles, SubDir))
        print("Train / Test / Validation sets for %s = %f %%  / %f %% / %f %%" % (SubDir, pTrain, pTest, pValid))
