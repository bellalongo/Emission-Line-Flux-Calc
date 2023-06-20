# Necessary imports
import astropy.io.fits as fits
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from scipy.signal import find_peaks, peak_widths
import astropy.units as u
import numpy as np
import pandas as pd
import math
import sys
from datetime import date
from collections import defaultdict
from astropy.table import QTable, Table, Column
from doppler_shift_calculator import *
from flux_calc import *
from emission_lines import *


# UPDATE INFO FOR EACH SPECTRA
filename = 'spectra/hlsp_muscles_hst_stis_tau_ceti_e140m_v1_component-spec.fits'  # PUT FILENAME HERE (make sure is in same directory)
grating = "e140m" # PUT GRATING HERE
star_name = "tau ceti" # PUT NAME OF STAR HERE
date = str(date.today())

# Fetch data
grating = grating.upper()
star_name = star_name.upper()
data = fits.getdata(filename)
w, f , e, dq = data['WAVELENGTH'], data['FLUX'], data['ERROR'], data['DQ']
mask = (w > 1160) 

# Find peaks
if grating == "G140L":
    peaks, properties = find_peaks(f[mask], height = 0.7*sum(f[mask])/len(f[mask]),  width = 0)
elif grating == "E140M":
    peaks, properties  = find_peaks(f[mask], height = 10*sum(f[mask])/len(f[mask]), prominence = 10*sum(f[mask])/len(f[mask]), width = 0, threshold = (1/10)*sum(f[mask])/len(f[mask]))
else:
    sys.exit("Invalid grating")

# Load Rest Lam data
data = pd.read_csv("../DEM_goodlinelist .csv")
rest_lam_data = pd.DataFrame(data)

# Find the average width of the peaks
peak_width, peak_width_pixels, flux_range = peak_width_finder(grating, w[mask])

# Find the doppler shift
doppler_shift = doppler_shift_calc(rest_lam_data, w[mask][peaks], flux_range)

# Initializing necessary variables
flux = defaultdict(list)
count = 0 
iterations = 0
previous_obs = 0 *u.AA
prev_blended_bool = False
prev_left_bound = 0
emission_lines_list = []

# Find the emission lines
for wavelength in rest_lam_data['Wavelength']:
    if(wavelength > 1160):     
        # obs_lam calculation from doppler
        rest_lam = wavelength * u.AA
        obs_lam = doppler_shift.to(u.AA,  equivalencies=u.doppler_optical(rest_lam))
        
        # Check for blended lines
        blended_line_bool = blended_line_check(previous_obs, obs_lam, iterations, flux_range)
        # Check if previous lam was also a blended line
        if blended_line_bool and prev_blended_bool:
            wavelength_mask = (w > prev_left_bound) & (w < (obs_lam.value + flux_range))
            prev_blended_bool = True
            emission_lines_list.pop()
        # If there is a blended line, and previous wasn't a blended line
        elif blended_line_bool:
            wavelength_mask = (w > (previous_obs.value - flux_range)) & (w < (obs_lam.value + flux_range))
            prev_blended_bool = True
            prev_left_bound = previous_obs.value - flux_range
            emission_lines_list.pop()
        # Not a blended line
        else:
            wavelength_mask = (w > (obs_lam.value - flux_range)) & (w < (obs_lam.value + flux_range))
            prev_blended_bool = False
        
        # Append emission line
        emission_lines_list.append(emission_line(wavelength, obs_lam, wavelength_mask, False, blended_line_bool))
    
        # Update variables
        previous_obs = obs_lam
        previous_index = len(flux[rest_lam_data['Ion'][count]]) - 1
        iterations+=1

# Determine if the current emission line is noise
for line in emission_lines_list:
    # Find the continuum
    continuum = []
    continuum_array = split_create_trendline(w[line.flux_mask], f[line.flux_mask], line.blended_bool, peak_width_pixels)

    # Create basic plot
    fig = plt.figure(figsize=(14,7))
    ax = fig.add_subplot()
    fig.suptitle('Click "y" if noise, "n" if not', fontsize=14, fontweight='bold')
    plt.title("Flux vs Wavelength for " + star_name)
    plt.xlabel('Wavelength (\AA)')
    plt.ylabel('Flux (erg s$^{-1}$ cm$^{-2}$ \AA$^{-1}$)')
    plt.ylabel('Flux (erg s$^{-1}$ cm$^{-2}$ \AA$^{-1}$)')
    trendline_patch = patches.Patch(color='darkorange', alpha=0.5, label='Flux Trendline')

    # Plot emission lines
    ax.plot(w[line.flux_mask], f[line.flux_mask], color="steelblue")
    ax.plot(w[line.flux_mask], continuum_array, color="darkorange", alpha=0.7)
    cid = fig.canvas.mpl_connect('key_press_event',on_key)
    plt.legend(handles=[trendline_patch])
    plt.show()

    # Calculate the flux and error
    w0,w1 = wavelength_edges(w[line.flux_mask])
    total_sumflux = np.sum(f[line.flux_mask]*(w1-w0))
    sumerror = (np.sum(e[line.flux_mask]**2 * (w1-w0)**2))**0.5

    # Calculate the continuum
    for i in range(0, len(continuum_array)):
        continuum.append(continuum_array[i])
    continuum_sumflux = np.sum(continuum*(w1-w0))

    # Check if noise
    total_flux = total_sumflux - continuum_sumflux
    if noise_bool_list[count]:
        # Update emission line's noise bool
        line.noise_bool = noise_bool_list[count]
        # Update flux calculation
        total_flux = sumerror * (-3)
        sumerror = 0

    # Append to flux list
    flux[rest_lam_data['Ion'][count]].append(("Wavelength: " + str(line.wavelength),"Flux: " + str(total_flux), "Error: " + str(sumerror),"Blended line: " + str(line.blended_bool)))

    count+=1 

# Plot the emission lines and trendlines
plt.figure(figsize=(14,10))
plt.plot(w[mask], f[mask], color="steelblue")
count = 0

for line in emission_lines_list:
    continuum_array = split_create_trendline(w[line.flux_mask], f[line.flux_mask], line.blended_bool, peak_width_pixels)

    if line.noise_bool:
        line_color = 'darkgreen'
    else:
        line_color = 'yellowgreen'

    plt.axvline(x=line.obs_lam.value, color= line_color, alpha=0.5)
    trendline, = plt.plot(w[line.flux_mask], continuum_array, color="darkorange", alpha=0.7)

    count+=1

# Create basic plot
plt.title("Flux vs Wavelength for " + star_name)
plt.xlabel('Wavelength (\AA)')
plt.ylabel('Flux (erg s$^{-1}$ cm$^{-2}$ \AA$^{-1}$)')
plt.ylabel('Flux (erg s$^{-1}$ cm$^{-2}$ \AA$^{-1}$)')

# Create plot legend
emission_patch = patches.Patch(color='yellowgreen', alpha=0.7, label='Emission Line')
noise_patch = patches.Patch(color='darkgreen', alpha=0.5, label='Noise')
trendline_patch = patches.Patch(color='darkorange', alpha=0.5, label='Flux Trendline')
plt.legend(handles=[emission_patch, noise_patch, trendline_patch])
plt.show()

# Create a fits file
data_array = []
fits_filename = star_name.lower() + ".fits"

for ion in flux:
    for data in flux[ion]:
        data_array.append({"Ion": ion, "Wavelength": data[0], "Flux": data[1], "Error": data[2], "Blended line": data[3]})

t = Table(rows=data_array)
t.write(fits_filename, overwrite=True) 

# Update header
with fits.open(fits_filename, mode='update') as hdul:
    hdr = hdul[0].header
    hdr.set('DATE', date, 'date flux was calculated')
    hdr.set('FILENAME', filename, 'name of the fits file used to calculate the flux')
    hdr.set('FILETYPE', "SCI", 'file type of fits file')
    hdr.set('TELESCP', "HST", 'telescope used to measure flux')
    hdr.set('INSTRMNT', "SCIS", 'active instrument to measure flux')
    hdr.set('GRATING', grating, 'grating used to measure flux')
    hdr.set('TARGNAME', star_name, 'name of star used in measurement')
    hdr.set('DOPPLER', str(doppler_shift.value) + " km/s", 'doppler shift used to measure flux')
    hdr.set('WIDTH', "+/- " + str(peak_width) + " Angstroms", 'peak_width used to measure flux')
    hdr.set('RANGE', "+/- " + str(flux_range) + " Angstroms", 'flux range used to measure flux')
    hdr.set('WIDTHPXL', peak_width_pixels, 'peak_width in pixels used to measure flux')
    hdr.set('UPRLIMIT', 3*sumerror, 'upper limit used to determine noise')
    hdul.flush() 

# Printing
for ion in flux:
    print(f"Ion: {ion} ")
    for data in flux[ion]:
        print(data)