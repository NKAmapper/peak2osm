#!/usr/bin/env python
# -*- coding: utf8

# peak2osm.py
# Merges OSM, N50 and SSR peaks
# Usage: peak2osm.py <municipality name>


import json
import sys
import os
import math
import urllib.request
import zipfile
from io import BytesIO
from xml.etree import ElementTree as ET
import utm  # In N50 repo


version = "1.0.0"

header = {"User-Agent": "nkamapper/n50osm"}

import_folder = "~/Jottacloud/osm/stedsnavn/"  # Folder containing import SSR files (default folder tried first)

overpass_api = "https://overpass-api.de/api/interpreter"  # Overpass endpoint

max_offset = 1000  # Max BBOX size in meters

debug = False



# Output message

def message (output_text):

	sys.stdout.write (output_text)
	sys.stdout.flush()



# Compute approximation of distance between two coordinates, (lon,lat), in meters
# Works for short distances

def distance (point1, point2):

	lon1, lat1, lon2, lat2 = map(math.radians, [point1[0], point1[1], point2[0], point2[1]])
	x = (lon2 - lon1) * math.cos( 0.5*(lat2+lat1) )
	y = lat2 - lat1
	return 6371000.0 * math.sqrt( x*x + y*y )  # Metres



# Calculate new node with given distance offset in meters
# Works over short distances

def coordinate_offset (node, offset):

	m = (1 / ((math.pi / 180.0) * 6378137.0))  # Degrees per meter

	latitude = node[1] + (offset * m)
	longitude = node[0] + (offset * m) / math.cos( math.radians(node[1]) )

	return (longitude, latitude)



# Returns bbox around given node with given offset

def create_bbox (node, offset):

	bbox = [ coordinate_offset(node, - offset), coordinate_offset(node, + offset) ]

	return bbox


 
# Calculate Jaro Similarity of two strings
# Source: https://www.geeksforgeeks.org/jaro-and-jaro-winkler-similarity/

def jaro_distance(s1, s2):
 
	if s1 == s2:
		return 1.0
 
	len1 = len(s1)
	len2 = len(s2)
 
	if len1 == 0 or len2 == 0:
		return 0.0
 
	# Maximum distance upto which matching is allowed 
	max_dist = (max(len(s1), len(s2)) // 2 ) - 1
 
	# Count of matches 
	match = 0
 
	# Hash for matches 
	hash_s1 = [0] * len(s1)
	hash_s2 = [0] * len(s2)
 
	# Traverse through the first string 
	for i in range(len1): 
 
		# Check if there is any matches 
		for j in range( max(0, i - max_dist), min(len2, i + max_dist + 1) ): 
			 
			# If there is a match 
			if (s1[i] == s2[j] and hash_s2[j] == 0): 
				hash_s1[i] = 1
				hash_s2[j] = 1
				match += 1
				break
		 
	# If there is no match 
	if match == 0:
		return 0.0
 
	# Number of transpositions 
	t = 0
 
	point = 0
 
	# Count number of occurrences where two characters match but there is a third matched character in between the indices 
	for i in range(len1): 
		if hash_s1[i]:
 
			# Find the next matched character 
			# in second string 
			while hash_s2[point] == 0:
				point += 1
 
			if s1[i] != s2[point]:
				point += 1
				t += 1
			else :
				point += 1
				 
		t /= 2
 
	# Return the Jaro Similarity 
	return (match / len1 + match / len2 + (match - t) / match ) / 3.0
 


# Calculate Jaro Winkler Similarity 

def jaro_winkler_distance(s1, s2): 
 
	jaro_dist = jaro_distance(s1, s2)
 
	# If the jaro Similarity is above a threshold 
	if jaro_dist > 0.7:
 
		# Find the length of common prefix 
		prefix = 0
 
		for i in range(min(len(s1), len(s2))):
		 
			# If the characters match 
			if s1[i] == s2[i]:
				prefix += 1
 
			# Else break 
			else:
				break
 
		# Maximum of 4 characters are allowed in prefix 
		prefix = min(4, prefix)
 
		# Calculate jaro winkler Similarity 
		jaro_dist += 0.1 * prefix * (1 - jaro_dist)
 
	return jaro_dist



# Compare names in given tags using Jaro Winkler distance

def compare_names(tags1, tags2):

	name_tags = ["name", "alt_name", "old_name", "loc_name", "official_name"]

	name_keys1 = []
	name_keys2 = []

	for key in tags1:
		prefix_key = key.split(":")[0]
		if prefix_key in name_tags:
			name_keys1.append(key)

	for key in tags2:
		prefix_key = key.split(":")[0]
		if prefix_key in name_tags:
			name_keys2.append(key)

	if not name_keys1 or not name_keys2:
		return 2.0

	jw_max = 0.0
	for key1 in name_keys1:
		for value1 in tags1[ key1 ].split(";"):
			for key2 in name_keys2:
				for value2 in tags2[ key2 ].split(";"):
					jw = jaro_winkler_distance(value1, value2)
					jw_max = max(jw_max, jw)

	if debug and jw_max < 1:
		logfile.write("%.3f\n" % jw)
		logfile.write("%s\n" % str([tags1[key] for key in tags1 if "name" in key ]))
		logfile.write("%s\n" % str([tags2[key] for key in tags2 if "name" in key ]))
		logfile.write("\n")

	return jw_max



# Get name or id of municipality from GeoNorge api

def get_municipality (query):

	if query.isdigit():
		url = "https://ws.geonorge.no/kommuneinfo/v1/kommuner/" + query
	else:
		url = "https://ws.geonorge.no/kommuneinfo/v1/sok?knavn=" + urllib.parse.quote(query)

	request = urllib.request.Request(url, headers=header)

	try:
		file = urllib.request.urlopen(request)
	except urllib.error.HTTPError as e:
		if e.code == 404:  # Not found
			sys.exit("\tMunicipality '%s' not found\n\n" % query)
		else:
			raise

	if query.isdigit():
		result = json.load(file)
		file.close()
		municipality_name = result['kommunenavnNorsk']
		return (query, municipality_name)

	else:
		result = json.load(file)
		file.close()
		if result['antallTreff'] == 1:
			municipality_id = result['kommuner'][0]['kommunenummer']
			municipality_name = result['kommuner'][0]['kommunenavnNorsk']
			return (municipality_id, municipality_name)
		else:
			municipalities = []
			for municipality in result['kommuner']:
				municipalities.append(municipality['kommunenummer'] + " " + municipalities['kommunenavnNorsk'])
			sys.exit("\tMore than one municipality found: %s\n\n" % ", ".join(municipalities))



# Get tags of OSM or N50 element (XML data structure)

def get_tags(xml_element):

	tags = {}
	for tag in xml_element.findall("tag"):
		tags[ tag.attrib['k'] ] = tag.attrib['v']	

	# Check if "m" (meter) has been added to elevation, and remove it 

	if "ele" in tags:
		new_ele = tags['ele'].rstrip("m. ").strip()
		if new_ele != tags['ele']:
			tags['ele'] = new_ele
			xml_element.set("action", "modify")

	return tags



# Load peak names from SSR

def load_ssr_peak_names():

	message ("\tLoad SSR peak names ... ")

	filename = "stedsnavn_%s_%s.geojson" % (municipality_id, municipality_name.replace(" ", "_"))
	file = open(os.path.expanduser(import_folder + filename))
	ssr_data = json.load(file)
	file.close()

	for feature in ssr_data['features'][:]:
		if "GRUPPE" in feature['properties'] and feature['properties']['GRUPPE'] == "høyder":
			tags = {}
			for key, value in iter(feature['properties'].items()):
				if key == "N50" or key != key.upper():  # Remnove uppercase tags
					tags[ key ] = value
				elif key == "TYPE":
					tags['SSR_TYPE'] = value
#			if tags['SSR_TYPE'] == "hei":
#				tags['natural'] = "ridge"  # Override tagging
			element = {
				'point': feature['geometry']['coordinates'],
				'tags': tags,
				'bbox': create_bbox(feature['geometry']['coordinates'], max_offset)
			}
			ssr_peaks.append(element)

		if feature['properties']['GRUPPE'] != "høyder":  # For source output
			ssr_data['features'].remove(feature)

	message ("%i peak names loaded\n" % len(ssr_peaks))

	# Save SSR file for debugging

	if debug:
		filename = "ssr_%s_peaks_source.geojson" % municipality_name.replace(" ", "_")
		file = open(filename, "w")
		json.dump(ssr_data, file, indent=2, ensure_ascii=False)
		file.close()



# Load peaks from N50 file (OSM format)

def load_n50_peaks_from_file():

	message ("\tLoad N50 peaks ... ")

	filename = "n50_%s_%s_Hoyde.osm" % (municipality_id, municipality_name.replace(" ", "_"))
	file = open(filename)
	osm_data = file.read()
	file.close()

	n50_root = ET.fromstring(osm_data)
	n50_tree = ET.ElementTree(n50_root)

	for node in n50_root.iter("node"):
		point = ( float(node.attrib['lon']), float(node.attrib['lat']) )
		element = {
			'point':point,
			'tags': get_tags(node),
			'bbox': create_bbox(point, max_offset)
		}
		element['tags']['natural'] = "hill"
		n50_peaks.append(element)

	message ("%i peaks loaded\n" % len(n50_peaks))




# Load peak data from N50 api (also works for N100)

def load_n50_peaks():

	# Parse WKT string into list of (lon, lat) coordinate tuples.
	# Convert from UTM 33N.

	def parse_coordinates(wkt):

		split_wkt = wkt.split(" ")
		coordinates = []
		for i in range(0, len(split_wkt) - 1, 2):
			x = float(split_wkt[ i ])
			y = float(split_wkt[ i + 1 ])
			lat, lon = utm.UtmToLatLon (x, y, 33, "N")
			node = (round(lon, 7), round(lat, 7))
			coordinates.append(node)

		return coordinates


	# Convert filename characters to Kartverket standard.

	def clean_filename(filename):

		return filename.replace("Æ","E").replace("Ø","O").replace("Å","A")\
						.replace("æ","e").replace("ø","o").replace("å","a").replace(" ", "_")


	message ("\tLoad N50 peaks from Kartverket ... ")

	# Load latest N50 file for municipality from Kartverket

	if municipality_name == "Nesbyen":
		filename1 = "Basisdata_3322_Nesbyen_25833_N50Kartdata_GML"
	else:
		filename1 = clean_filename("Basisdata_%s_%s_25833_N50Kartdata_GML" % (municipality_id, municipality_name))
	url = "https://nedlasting.geonorge.no/geonorge/Basisdata/N50Kartdata/GML/%s.zip" % filename1

	request = urllib.request.Request(url, headers=header)
	file_in = urllib.request.urlopen(request)
	zip_file = zipfile.ZipFile(BytesIO(file_in.read()))

	filename2 = filename1.replace("Kartdata", "Hoyde")
	file = zip_file.open(filename2 + ".gml")

	tree = ET.parse(file)
	file.close()
	file_in.close()
	root = tree.getroot()

	ns_gml = 'http://www.opengis.net/gml/3.2'
	ns_app = "https://skjema.geonorge.no/SOSI/produktspesifikasjon/N50/20230401"

	ns = {
		'gml': ns_gml,
		'app': ns_app
	}

	# Loop points and store in dict

	count = 0

	for feature_type in ["Terrengpunkt", "TrigonometriskPunkt"]:
		for feature in root.findall(".//app:" + feature_type, ns):
			point_wkt = feature.find(".//gml:pos", ns).text
			point = parse_coordinates(point_wkt)[0]
			height = feature.find(".//app:høyde", ns).text

			element = {
				'point': point,
				'tags': {
					'natural': 'hill',
					'ele': height
				},
				'bbox': create_bbox(point, max_offset)
			}
			if feature_type == "TrigonometriskPunkt":
				element['tags']['man_made'] = "survey_point"
			n50_peaks.append(element)
			count += 1

	message ("%i peaks loaded\n" % count)

	# Save to file for debugging

	if debug:
		features = []
		for peak in n50_peaks:
			feature = {
				'type': 'Feature',
				'properties': peak['tags'],
				'geometry': {
					'type': 'Point',
					'coordinates': [ peak['point'][0], peak['point'][1] ]
				}
			}
			features.append(feature)

		collection = {
			'type': 'FeatureCollection',
			'features': features
		}

		filename = "n50_%s_peaks_source.geojson" % municipality_name.replace(" ", "_")
		file = open(filename, "w")
		json.dump(collection, file, indent=2, ensure_ascii=False)
		file.close()



# Load existing peaks in OSM

def load_osm_peaks():

	global osm_root, osm_tree

	message ("\tLoad existing OSM peaks from Overpass ...")

	area_query = '[ref=%s][admin_level=7][place=municipality]' % municipality_id

	query = ('[timeout:200];'
				'(area%s;)->.a;'
				'('
					'nwr["natural"="peak"](area.a);'
					'nwr["natural"="hill"](area.a);'
					'nwr["natural"="cliff"](area.a);'
					'nwr["natural"="mountain_range"](area.a);'
					'nwr["natural"="ridge"](area.a);'
					'nwr["tourism"="viewpoint"](area.a);'
				');'
				'(._;>;<;);'
				'out meta;' % area_query)

	request = urllib.request.Request(overpass_api + "?data=" + urllib.parse.quote(query), headers=header)
	try:
		file = urllib.request.urlopen(request)
	except urllib.error.HTTPError as err:
		sys.exit("\n\n\t*** %s\n\n" % err)
	data = file.read()
	file.close()

	osm_root = ET.fromstring(data)
	osm_tree = ET.ElementTree(osm_root)

	for node in osm_root.iter("node"):
		tags = get_tags(node)
		if "natural" in tags and tags['natural'] in ['peak', 'hill', 'mountain_range', 'ridge']:
			point = ( float(node.attrib['lon']), float(node.attrib['lat']) )
			element = {
				'point': point,
				'tags': tags,
				'bbox': create_bbox(point, max_offset),
				'xml': node
			}
			osm_peaks.append(element)

	message ("%i peaks loaded\n" % len(osm_peaks))

	if debug:
		filename = "osm_%s_peaks_source.osm" % municipality_name.replace(" ", "_")
		osm_root.set("upload", "false")
		osm_tree.write(filename, encoding='utf-8', method='xml', xml_declaration=True)	



# Match and merge peaks

def match_peaks():

	# Create list of matches within given offset

	def create_matches (peaks1, peaks2, offset):

		matches = []

		for peak1 in peaks1:
			if "match" not in peak1:
				for peak2 in peaks2:
					if ("match" not in peak2
							and peak2['bbox'][0][0] < peak1['point'][0] < peak2['bbox'][1][0]
							and peak2['bbox'][0][1] < peak1['point'][1] < peak2['bbox'][1][1]):
						gap = distance(peak1['point'], peak2['point'])
						if gap < offset:
							match = {
								'1': peak1,
								'2': peak2,
								'gap': gap
							}
							matches.append(match)

		matches.sort(key=lambda m: m['gap'])  # Sort according to distance

		return matches


	# Update tags in OSM with data from source

	def update_tags(osm_peak, source_peak):

		modify = False
		for key, value in iter(source_peak['tags'].items()):
			if key in osm_peak['tags']:
				# Update existing tag
				if value != osm_peak['tags'][ key ]:
					if key == "GAP":  # Keep largest
						value = str(max(int(osm_peak['tags']['GAP']), int(ource_peak['tags']['GAP'])))
					elif key == "CHECK":  # Keep smallest
						value = str(min(int(osm_peak['tags']['CHECK']), int(source_peak['tags']['CHECK'])))
					else:
						osm_peak['xml'].append(ET.Element("tag", k="OSM_" + key, v=osm_peak['tags'][ key ]))
					tag_xml = osm_peak['xml'].find("tag[@k='%s']" % key)
					tag_xml.set("v", value)
					modify = True
			else:
				# Add new tag
				osm_peak['xml'].append(ET.Element("tag", k=key, v=value))
				modify = True

		# Remove place=locality if natural=peak as new tag
		if ("natural" in source_peak['tags'] and source_peak['tags']['natural'] == "peak"
				and "place" in osm_peak['tags'] and osm_peak['tags']['place'] == "locality"):
			tag_xml = osm_peak['xml'].find("tag[@k='place']")
			osm_peak['xml'].remove(tag_xml)
			del osm_peak['tags']['place']
			modify = True

		if modify:
			osm_peak['xml'].set("action", "modify")
			osm_peak['tags'].update(source_peak['tags'])


	# Add tag to OSM (XML structure)

	def add_tag(osm_peak, key, value):

		osm_peak['xml'].append(ET.Element("tag", k=key, v=value))
		osm_peak['xml'].set("action", "modify")
		osm_peak['tags'][ key ] = value


	# Get existing elevation, if any

	def elevation(osm_peak):

		if "ele" not in osm_peak['tags']:
			return -100
		if osm_peak['tags']['ele'].replace(".", "", 1).isdigit():
			return float(osm_peak['tags']['ele'])


	message ("Merging peaks ...\n")

	# 1. Check close SSR names within 50 meters (potential duplicates or alternative names)

	matches = create_matches(ssr_peaks, ssr_peaks, 50)

	close = 0
	for match in matches:
		ssr_peak1 = match['1']
		ssr_peak2 = match['2']	

		if ssr_peak1 != ssr_peak2 and "CLOSE" not in ssr_peak1['tags'] and "CLOSE" not in ssr_peak2['tags']:
			ssr_peak1['tags']['CLOSE'] = str(int(match['gap']))
			close += 1

	message ("\tFound %i close SSR peaks - potential duplicates\n" % close)


	# 2. Check potential duplicate OSM/SSR names

	matches = create_matches(osm_peaks, osm_peaks, 1000)

	duplicate = 0
	tested = set()

	for match in matches:
		osm_peak1 = match['1']
		osm_peak2 = match['2']	

		if (osm_peak1 != osm_peak2
				and "DUPLICATE" not in osm_peak1['tags']
				and "DUPLICATE" not in osm_peak2['tags']
				and (osm_peak2['xml'], osm_peak1['xml']) not in tested):
			jw = compare_names(osm_peak1['tags'], osm_peak2['tags'])
			tested.add( (osm_peak1['xml'], osm_peak2['xml']) )
			if 0.9 <= jw <= 1:
				add_tag(osm_peak1, "DUPLICATE", str(int(match['gap'])))
				add_tag(osm_peak1, "JARO_WINKLER", "%.3f" % jw)
				duplicate += 1

	message ("\tFound %i duplicate peaks in OSM\n" % close)


	# 3. Match SSR peaks with OSM peaks

	matches = create_matches(ssr_peaks, osm_peaks, 1000)

	ssr_matched = 0
	duplicate = 0

	for match in matches:
		ssr_peak = match['1']
		osm_peak = match['2']
		if "match" not in ssr_peak and "match_name" not in osm_peak:
			jw = compare_names(ssr_peak['tags'], osm_peak['tags'])
			if match['gap'] < 300:
				if jw >= 0.9:
					update_tags(osm_peak, ssr_peak)
					add_tag(osm_peak, "GAP", str(int(match['gap'])))
					if jw <= 1:
						add_tag(osm_peak, "JARO_WINKLER", "%.3f" % jw)

					ssr_peak['match'] = "OSM"
					osm_peak['match_name'] = "SSR"
					ssr_matched += 1

				else:
					add_tag(osm_peak, "CHECK", str(int(match['gap'])))  # Manual inspection needed

			elif 0.9 <= jw <= 1:
				add_tag(osm_peak, "DUPLICATE", str(int(match['gap'])))
				add_tag(osm_peak, "JARO_WINKLER", "%.3f" % jw)
				duplicate += 1

	message ("\tFound %i potential duplicates across SSR/OSM\n" % duplicate)	
	message ("\tMatched %i SSR peak names with OSM\n" % ssr_matched)


	# 4. Match N50 peaks with OSM peaks

	matches = create_matches(n50_peaks, osm_peaks, 300)

	n50_matched = 0
	for match in matches:
		n50_peak = match['1']
		osm_peak = match['2']
		if "match" not in n50_peak and "match_ele" not in osm_peak:

			if (match['gap'] < 50
					and ("man_made" not in n50_peak['tags'] or n50_peak['tags']['man_made'] != "survey_point" or match['gap'] < 25)
					and ("ele" not in osm_peak['tags'] or abs(elevation(osm_peak) - int(n50_peak['tags']['ele'])) <= 2)):
				if "match_name" in osm_peak and "natural" in osm_peak['tags'] and osm_peak['tags']['natural'] == "peak":
					del n50_peak['tags']['natural']
				update_tags(osm_peak, n50_peak)
				add_tag(osm_peak, "GAP", str(int(match['gap'])))
				n50_peak['match'] = "OSM"
				osm_peak['match_ele'] = "N50"
				n50_matched += 1

			else:
				add_tag(osm_peak, "CHECK", str(int(match['gap'])))  # Manual inspection needed

	message ("\tMatched %i N50 peaks with OSM\n" % n50_matched)


	# 5. Convert remaining peaks in OSM to hill

	count = 0
	for osm_peak in osm_peaks:
		if "match_ele" not in osm_peak and "match_name" not in osm_peak:
			if "natural" in osm_peak['tags'] and osm_peak['tags']['natural'] == "peak":
				osm_peak['tags']['natural'] = "hill"
				tag_xml = osm_peak['xml'].find("tag[@k='natural']")
				tag_xml.set("v", "hill")
				add_tag(osm_peak, "OSM_natural", "peak")
				count += 1

	message ("\tConverted remaining %i peaks to hill\n" % count)


	# 6. Match remaining SSR peak names with remaining N50 peaks

	matches = create_matches(n50_peaks, ssr_peaks, 300)

	ssr_matched = 0
	for match in matches:
		n50_peak = match['1']
		ssr_peak = match['2']
		if "match" not in ssr_peak and "match" not in n50_peak and "match_name" not in n50_peak:
			if match['gap'] < 100:
				n50_peak['tags'].update(ssr_peak['tags'])
				n50_peak['tags']['GAP'] = str(int(match['gap']))
				ssr_peak['match'] = "N50"
				n50_peak['match_name'] = "SSR"
				ssr_matched += 1
			else:
				ssr_peak['tags']['CHECK'] = str(int(match['gap']))  # Manual inspectio needed

	message ("\tMatched %i SSR peak names with N50\n" % ssr_matched)


	# 7. Add remaining peaks from N50 and SSR

	added = 0
	osm_id = -1000
	for peak in n50_peaks + ssr_peaks:
		if "match" not in peak:
			osm_id -= 1
			node = ET.Element("node", id=str(osm_id), action="modify", lat=str(peak['point'][1]), lon=str(peak['point'][0]))
			for key, value in iter(peak['tags'].items()):
				node.append(ET.Element("tag", k=key, v=value))
			osm_root.append(node)
			added += 1

	message ("\tAdded remaining %i peaks from N50 and SSR\n" % added)



# Save merged file

def save_file():

	filename = "peaks_%s_%s.osm" % (municipality_id, municipality_name.replace(" ", "_"))

	osm_root.set("generator", "peak2osm")
	osm_root.set("upload", "false")
	osm_tree.write(filename, encoding='utf-8', method='xml', xml_declaration=True)

	message ("Saved to file '%s'\n" % filename)



# Main program

if __name__ == '__main__':

	message ("\n")

	# Get municipality

	if len(sys.argv) > 1:
		municipality_id, municipality_name = get_municipality(sys.argv[1])
	else:
		sys.exit("Please enter municipality name or number\n")

	# Load data

	ssr_peaks = []
	n50_peaks = []
	osm_peaks = []

	message ("Loading data ...\n")

	if debug:
		logfile = open("jw.txt", "w")

	load_ssr_peak_names()
	load_n50_peaks()
	load_osm_peaks()

	match_peaks()

	save_file()

	if debug:
		logfile.close()

	message ("\n")

