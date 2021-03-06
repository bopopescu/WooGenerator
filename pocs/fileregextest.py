import tempfile
import os
import re
import csv

in_folder = "../input/"
test_path = os.path.join(in_folder, "insane.csv")

sub_params = None
sub_params = {
    'pattern': r',"([^"]*)\n([^"]*)",',
    'repl': r',"\1\\n\2",'
}

with open(test_path) as testFile:
    if sub_params:
        with tempfile.TemporaryFile() as tempFile:
            tempFile.write(re.sub(sub_params.get('pattern'),
                                  sub_params.get('repl'), testFile.read()))
            tempFile.seek(0)
            reader = csv.reader(tempFile)
            for row in reader:
                print row
    else:
        reader = csv.reader(testFile)
        for row in reader:
            print row
