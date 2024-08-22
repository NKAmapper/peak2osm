# peak2osm
Merge peak names and elevations from Kartverket to OSM in Norway

### Usage ###

<code>python peak2osm.py \<municipality\></code>

### Workflow ###

This script merges peak names from Kartverket SSR and elevations from Kartverket N50 with existing peaks in OSM.

Typical workflow:

1. Run _peaks2osm_ for a given municipality

   It will produce three source files for reference in addition to the merged file (for example named _peaks_3430_Os.osm_):
   * Current OSM peaks
   * N50 peaks
   * SSR peaks

3. Handle potential duplicates
   * Search for <code>DUPLICATE</code> to discover identical or similar names within a distance of 1000 meters.
   * Merge names or remove duplicate.

4. Handle close peaks with conflicting names
   * Search for <code>CLOSE</code> to discover close peaks (within 50 meters) which have different names.
   * Determine how alternative names for the same peak should be tagged, for example using **alt_name=***, or if the peaks could be slightly relocated.

5. Check close peaks without conflicting names
   * Search for <code>CHECK</code> to discover other close peaks (within 300 meters).
   * Determine if the peaks should be merged or slightly relocated.

6. Check merged peaks
   * Search for example <code>GAP>50</code> to check if the merged peak now have the correct location. The number represents the gap in meters.

7. Check tagging for certain peak types
    * <code>SSR_TYPE=berg</code> - Check if **natural=cliff** is a better tag.
    * <code>SSR_TYPE=rygg</code> - Check **natural=hill** vs **natural=ridge**.
    * <code>SSR_TYPE=hei or SSR_TYPE=ås</code> - Check for a better location or **natural=ridge** as these names often have a fuzzy location.

8. Check for dupliactes across the municipality boundary
    * Search for <code>new</code> and select OpenStreetMap as background imagery to discover any potential duplicates just across the municipality boundary.

9. Check natural=peak
    * With the Kartverket topo map as background imagery, check if more peaks should get **natural=peak** tagging.
    * You may want to use search using the **N50=*** tag to filter the most prominent peaks, as determined by Kartverket for N50.

10. Resolve tagging conflicts
    * <code>OSM_ele=*</code> - Contains the current elevation in OSM.
    * <code>OSM_name=*</code> - Contains the current spelling of **name=*** in OSM.
    * <code>OSM_place=peak</code> - Contains the current **place=*** tag in OSM.

11. Check place=locality
    * Remove for **natural=peak**
    * Remove if **name=*** is missing
    * Add for **natural=hill, cliff, ridge**
   
12. Upload to OSM
    * Remove remaining uppercase tags and upload to OSM.


### References ###

* [ssr2osm](https://github.com/NKAmapper/ssr2osm) på GitHub
* [n50osm](https://github.com/NKAmapper/n50osm) på GitHub
* [Kartverket SSR place name import wiki](https://wiki.openstreetmap.org/wiki/No:Import_av_stedsnavn_fra_SSR2)
* [Kartverket topo import wiki](https://wiki.openstreetmap.org/wiki/Import/Catalogue/Topography_import_for_Norway)
