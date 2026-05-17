import numpy as np

import ezc3d

# This example creates a dummy C3D file (with random data including unlabelled data to be removed).
# Then it reads it back and modifies it by removing the unlabelled data.
# That is to show how to modify a C3D file in memory and save it back.

# Create the c3d structure with some data
c3d = ezc3d.c3d()
c3d["parameters"]["POINT"]["RATE"]["value"] = [100]
c3d["parameters"]["POINT"]["LABELS"]["value"] = ("point1", "point2", "point3", "point4", "point5", "*unlabelled1", "*unlabelled2")
c3d["parameters"]["POINT"]["DESCRIPTIONS"]["value"] = ("desc1", "desc2", "desc3", "desc4", "desc5", "desc6", "desc7")
c3d["data"]["points"] = np.random.rand(3, 7, 100)
c3d["parameters"]["ANALOG"]["RATE"]["value"] = [1000]
c3d["parameters"]["ANALOG"]["LABELS"]["value"] = ("analog1", "analog2", "analog3", "analog4", "analog5", "analog6")
c3d["data"]["analogs"] = np.random.rand(1, 6, 1000)
c3d.write("temporary.c3d")

# Read the file back as if it was a file that someone wanted to modify
c3d_to_modify = ezc3d.c3d("temporary.c3d")

# Remove the unlabelled data
labels = c3d["parameters"]["POINT"]["LABELS"]["value"]
descriptions = c3d['parameters']['POINT']['DESCRIPTIONS']['value']
indices_to_keep = [i for i, lab in enumerate(labels) if not lab.startswith("*")]
c3d["parameters"]["POINT"]["LABELS"]["value"] = [labels[i] for i in indices_to_keep]
c3d["parameters"]["POINT"]["DESCRIPTIONS"]["value"] = [descriptions[i] for i in indices_to_keep]

# Change the data accordingly
c3d["data"]["points"] = c3d["data"]["points"][:, indices_to_keep, :]
del c3d["data"]["meta_points"]  # Let ezc3d do the job for the meta_points

# Save the modified file with a new name
c3d.write("temporary_modified.c3d")

# Read the modified file back and compare it to the original
c3d_modified = ezc3d.c3d("temporary_modified.c3d")
assert c3d_modified["parameters"]["POINT"]["LABELS"]["value"] == c3d["parameters"]["POINT"]["LABELS"]["value"]
assert c3d_modified["parameters"]["POINT"]["DESCRIPTIONS"]["value"] == c3d["parameters"]["POINT"]["DESCRIPTIONS"]["value"]
assert np.allclose(c3d_modified["data"]["points"][:3, :, :], c3d["data"]["points"])
