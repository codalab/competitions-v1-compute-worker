import os
import urllib
import urllib.request
import tempfile
import logging
import requests
import shutil
import yaml
from glob import glob

from zipfile import ZipFile


def _find_only_folder_with_metadata(path):
    """Looks through a bundle for a single folder that contains a metadata file and
    returns that folder's name if found"""
    files_in_path = os.listdir(path)
    if len(files_in_path) > 2 and 'metadata' in files_in_path:
        # We see more than a couple files OR metadata in this folder, leave
        return None
    for f in files_in_path:
        # Find first folder
        folder = os.path.join(path, f)
        if os.path.isdir(folder):
            # Check if it contains a metadata file
            if 'metadata' in os.listdir(folder):
                return folder


def get_available_memory():
    """Get available memory in megabytes"""
    mem_bytes = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
    mem_mib = mem_bytes / (1024. ** 2)
    return int(mem_mib)


def get_bundle(root_dir, relative_dir, url):
    # get file name from /test.zip?signature=!@#a/df
    url_without_params = url.split('?')[0]
    file_name = url_without_params.split('/')[-1]
    file_ext = os.path.splitext(file_name)[1]

    logging.debug("get_bundle :: Getting %s from %s" % (file_name, url))

    # Save the bundle to a temp file
    # file_download_path = os.path.join(root_dir, file_name)
    bundle_file = tempfile.NamedTemporaryFile(prefix='tmp', suffix=file_ext,
                                              dir=root_dir, delete=False)

    retries = 0
    while retries < 3:
        try:
            urllib.request.urlretrieve(url, bundle_file.name)
            break
        except Exception as e:
            retries += 1
            print(e)

    # Extracting files or grabbing extras
    bundle_path = os.path.join(root_dir, relative_dir)
    metadata_path = os.path.join(bundle_path, 'metadata')

    if file_ext == '.zip':
        logging.info("get_bundle :: Unzipping %s" % bundle_file.name)
        # Unzip file to relative dir, if a zip
        with ZipFile(bundle_file.file, 'r') as z:
            z.extractall(bundle_path)

        # check if we just unzipped something containing a folder and nothing else
        metadata_folder = _find_only_folder_with_metadata(bundle_path)
        if metadata_folder:
            logging.info(
                "get_bundle :: Found a submission with an extra folder, unpacking and moving up a directory")
            # Make a temp dir and copy data there
            temp_folder_name = os.join(root_dir, "%s%s" % (relative_dir, '_tmp'))
            try:
                shutil.copytree(metadata_folder, temp_folder_name)
            except shutil.Error as e:
                print(e)

            # Delete old dir, move copied data back
            shutil.rmtree(bundle_path, ignore_errors=True)
            shutil.move(temp_folder_name, bundle_path)

        # any zips we see should be unzipped to a folder with the name of the file
        for zip_file in glob(os.join(bundle_path, "*.zip")):
            name_without_extension = os.path.splitext(zip_file)[0]
            with ZipFile(os.join(bundle_path, zip_file), 'r') as z:
                z.extractall(os.join(bundle_path, name_without_extension))
    else:
        # Otherwise we have some metadata type file, like run.txt containing other bundles to fetch.
        os.mkdir(bundle_path)
        shutil.copyfile(bundle_file.name, metadata_path)

    os.chmod(bundle_path, 0o777)

    # Check for metadata containing more bundles to fetch
    metadata = None
    if os.path.exists(metadata_path):
        logging.info(
            "get_bundle :: Fetching extra files specified in metadata for {}".format(
                metadata_path))
        with open(metadata_path) as mf:
            metadata = yaml.load(mf)

    if isinstance(metadata, dict):
        for (k, v) in metadata.items():
            if k not in (
                    "description", "command", "exitCode", "elapsedTime", "stdout",
                    "stderr",
                    "submitted-by", "submitted-at"):
                if isinstance(v, str):
                    logging.debug(
                        "get_bundle :: Fetching recursive bundle %s %s %s" % (
                            bundle_path, k, v))
                    # Here K is the relative directory and V is the url, like
                    # input: http://test.com/goku?sas=123
                    metadata[k] = get_bundle(bundle_path, k, v)
    return metadata


def put_blob(url, file_path):
    logging.info("Putting blob %s in %s" % (file_path, url))
    requests.put(
        url,
        data=open(file_path, 'rb'),
        headers={
            'x-ms-blob-type': 'BlockBlob',
            'x-ms-version': '2018-03-28',
        }
    )


class ExecutionTimeLimitExceeded(Exception):
    pass


def alarm_handler(signum, frame):
    raise ExecutionTimeLimitExceeded
