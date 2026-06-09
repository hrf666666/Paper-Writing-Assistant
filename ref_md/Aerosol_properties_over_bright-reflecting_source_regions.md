---
title: "Aerosol properties over bright-reflecting source regions"
authors: "N.C. Hsu, Si-Chee Tsay, M.D. King, J.R. Herman"
journal: "IEEE Transactions on Geoscience and Remote Sensing"
doi: "10.1109/tgrs.2004.824067"
published: "March 2004"
source: "ieee_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 11348
---

# Aerosol properties over bright-reflecting source regions

**Abstract.** Retrieving aerosol properties from satellite remote sensing over a bright surface is a challenging problem in the research of atmospheric and land applications. In this paper we propose a new approach to retrieve aerosol properties over surfaces such as arid, semiarid, and urban areas, where the surface reflectance is usually very bright in the red part of visible spectrum and in the near infrared, but is much darker in the blue spectral region (i.e., wavelength <500 nm). In order to infer atmospheric properties from these data, a global surface reflectance database of 0.1/spl deg/ latitude by 0.1/spl deg/ longitude resolution was constructed over bright surfaces for visible wavelengths using the minimum reflectivity technique (e.g., finding the clearest scene during each season for a given location). The aerosol optical thickness and aerosol type are then determined simultaneously in the algorithm using lookup tables to match the satellite observed spectral radiances. Examples of aerosol optical thickness derived using this algorithm over the Sahara Desert and Arabian Peninsula reveal various dust sources, which are important contributors to airborne dust transported over long distances. Comparisons of the satellite inferred aerosol optical thickness and the values from ground-based Aerosol Robotic Network (AERONET) sun/sky radiometer measurements indicate good agreement (i.e., within 30%) over the sites in Nigeria and Saudi Arabia. This new algorithm, when applied to Moderate Resolution Imaging Spectroradiometer (MODIS), Sea-viewing Wide Field of view Sensor (SeaWiFS), and Global Imager (GLI) satellite data, will provide high spatial resolution (/spl sim/1 km) global information of aerosol optical thickness over bright surfaces on a daily basis.

## Introduction

Among ALL OF THE natural and manmade types of tropospheric aerosols, mineral aerosols (dust) play an important role in climate forcing throughout the entire year<sup>7, 14, 22</sup>. Due to their relatively short lifetime (a few hours to about a week), the distributions of these airborne dust particles vary extensively in both space and time. Consequently, satellite observations are needed over both source and sink regions for continuous temporal and spatial sampling of dust properties to study their climatic and health impact on regional and global scales. Several recent papers have modeled the direct forcing of such aerosols using optical properties of aerosols compiled from various measurements<sup>29, 33</sup>. However, these studies indicate that there are large uncertainties in estimating both shortwave and longwave climate forcing of mineral aerosols. Even the sign of the net forcing is not well determined.

Many authors have extensively investigated dust properties over ocean using satellite measurements<sup>27, 30, 34, 37</sup> as well as some measurements over dark vegetated areas<sup>18, 19</sup>. However, despite the importance of high spatial resolution satellite remote sensing measurements of dust near its source, where the underlying surface is usually bright, they are lacking because such measurements have been particularly difficult to make. Over these regions, the surface contribution to the radiance received by a satellite is larger than that over vegetated areas. Knowledge of dust absorption and the angular properties due to particle nonsphericity is also unknown. As a result, estimates of the climatic effect of dust near source regions are highly uncertain.

There have been several approaches developed to retrieve aerosol optical properties over the desert, including contrast reduction (atmospheric blurring) and thermal property techniques<sup>35, 36</sup>. However, since contrast reduction using visible wavelengths depends on the selection of highly contrasted areas as retrieval targets, this approach might not be straightforward for most desert regions. For thermal techniques, the separation of the signal due to mineral aerosols from that due to the background temperature and water vapor signals of the terrestrial environment can be difficult, particularly over semiarid regions. UV measurements from the Total Ozone Mapping Spectrometer (TOMS) instruments also provide valuable long-term information on the distribution of absorbing aerosols (such as dust and smoke) over land<sup>8, 12, 38</sup>. In spite of this advantage, however, the UV technique is very sensitive to the altitude of the aerosol plume<sup>13, 38</sup>, and the spatial resolution of the TOMS instrument is coarse (100 km average and 50 km at nadir).

The problem of retrieving aerosol properties over bright-reflecting surfaces using visible wavelengths is illustrated in Fig. 1. In essence, the upward radiance received by satellite (or apparent reflectance) is composed of the contribution from the light scattered by the atmosphere from the direct solar beam into the sensor's field of view without being reflected by the surface (i.e., atmospheric path radiance), and the contribution from the reflected radiation of both the direct and diffuse components by the surface. Therefore, the ability to retrieve aerosol properties depends on the relative roles that the atmosphere and surface play in radiance measurements by satellite.

![Figure 1](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-1-source-large.gif)

![Figure 1](/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-1-source-small.gif)

**Figure 1.** - Simulated apparent reflectance (atmosphere + surface) at the top of the atmosphere at 490 nm, as a function of surface reflectance for various values of the aerosol optical thickness $\tau_{\rm a}$ and single-scattering albedo $\omega_0$. The black solid line represents the apparent reflectance without aerosol, and the black dotted, green, and red lines represent the apparent reflectance with $\tau_{\rm a}=1.0$. The vertical lines denote the critical values of surface reflectance where the presence of aerosol cannot be detected by satellite for selected values of $\omega_0$.

Fig. 1 shows the simulated apparent reflectances at the top of atmosphere as a function of surface reflectance at 490 nm for aerosols with single-scattering albedos $(\omega_0)$ of 0.91, 0.96, and 1.0. The aerosol optical thickness $(\tau_{\rm a})=1.0$. If the aerosol is nonabsorbing [denoted by the black dotted line $(\omega_0=1.0)$], the contrast in apparent reflectance between the heavy dust and no dust condition is diminished over bright surfaces. Therefore, the apparent reflectance is not sensitive to changes in nonabsorbing aerosol loading over such surfaces. On the other hand, if the aerosol absorbs sunlight, its presence would brighten the total reflectance over dark targets and darken the reflectance over high reflecting targets, as indicated by the green

![Figure 2](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-2-source-large.gif)

![Figure 2](/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-2-source-small.gif)

**Figure 2.** - SeaWiFS images over northeast Africa on February 10, 2001. The dynamical ranges of the grayscale used in (b)–(d) are individually adjusted to optimize the appearance of atmospheric features against the background surfaces.

$(\omega_0=0.96)$

and red

$(\omega_0=0.91)$

lines. Since the critical values of surface reflectance (denoted by vertical dashed lines), where the total reflectance is not affected by the presence of aerosols, depend on the aerosol absorption

<sup>17, 20</sup>, retrievals of aerosol properties near these values contain large errors. Previous algorithms that use only wavelengths greater than 600 nm, therefore, have significant difficulty in retrieving aerosol properties over bright-reflecting surfaces.

This effect can be observed in the satellite imagery acquired over the Sahara Desert by the Sea-viewing Wide Field of view Sensor (SeaWiFS) (cf. Fig. 2). This scene covers areas over Morocco, part of the Atlantic coast, Algeria, Mauritania, and Mali as observed on February 10, 2001. The reflectance in the 670-nm band is significantly brighter than those at the 412- and 490-nm channels. We adjust the dynamical range of the grayscale used in these images from 412–670 nm to better contrast the atmospheric features against the background surfaces. According to the 412-nm image [Fig. 2(b)], a major dust plume occurred near the center of Algeria (on the right side of the image). Also observed were several narrow thin dust plumes near the border between Mauritania and Mali (on the center and left side of the image). However, these dust features become less discernible as the wavelength becomes greater and are actually impossible to discern at 670 nm [Fig. 2(d)] or longer wavelengths at which the surfaces are quite bright. Some of the thin plumes are completely indistinguishable in the 670-nm image.

Because of these difficulties, the resulting coverage of aerosol retrievals over desert areas is lacking in the current Moderate Resolution Imaging Spectroradiometer (MODIS) algorithm. MODIS instruments aboard the EOS Terra and Aqua spacecraft are uniquely designed (wide spectral range, high spatial resolution, and near daily global coverage) to study cloud and aerosol properties with high accuracy<sup>23</sup>. Fig. 3 shows the 2.1-$\mu\hbox {m}$ surface reflectance, or white-sky albedo, as a function of season derived from MODIS using the operational land algorithm<sup>28, 32</sup>. Operationally, MODIS aerosol retrievals over land use the dark-target approach<sup>18, 19</sup>, and no retrievals are performed when the 2.1-$\mu\hbox {m}$ surface reflectance is above 0.15. This means that MODIS currently provides no aerosol retrievals for large land areas, particularly over ones containing significant dust sources.

![Figure 3](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-3-source-large.gif)

![Figure 3](/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-3-source-small.gif)

**Figure 3.** - MODIS retrieved surface reflectance at 2.1 $\mu\hbox {m}$ for 16-day periods beginning (top left) in January 1, 2001, (top right) April 7, 2001, (bottom left) July 12, 2001, and (bottom right) September 30, 2001. Note the missing data due to persistent cloud cover or seasonal snow.

We have developed a new algorithm designed to retrieve aerosol properties over bright-reflecting surfaces using data from either SeaWiFS or the two MODIS instruments currently in orbit. The calibration and SNR of these sensors are sufficiently accurate to minimize sensor effects on our retrievals<sup>2, 23</sup>. Our algorithm, known as Deep Blue, alleviates the bright-surface problem outlined above by employing radiance measurements from the blue channels to infer the properties of aerosols. Both surface and cloud effects are accounted for in Deep Blue, and as shown later in this paper, the surface reflectance at 412 nm is below the critical values for dust in most desert regions. In the following sections, we will describe the Deep Blue algorithm and analyze its performance and error budget. We will also compare retrieved aerosol optical thicknesses over the Sahara Desert and Arabian Peninsula, calculated using Deep Blue and radiance measurements from SeaWiFS with optical thicknesses derived from ground-based sun photometer measurements.

## Description of the Deep Blue Algorithm

To retrieve aerosol properties over the desert, we employ a polarized radiative transfer model<sup>4</sup> to compute the reflected intensity field, which is defined by $$ $$R(\mu,\mu_{0},\phi)={\pi I(\mu,\mu_{0},\phi)\over\mu_{0}\ F_{0}}\eqno{\hbox{(1)}}$$ $$ where $R$ is the normalized radiance (or apparent reflectance), $F_{0}$ is the extraterrestrial solar flux, $I$ is the radiance at the top of the atmosphere, $\mu$ is the cosine of the view zenith angle, $\mu_{0}$ is the cosine of the solar zenith angle, and $\phi$ is the relative azimuth angle between the direction of propagation of scattered radiation and the incident solar direction.

In our algorithm, we assume that the underlying surface is Lambertian and homogeneous. As a result, the total radiance at the top of the atmosphere can be written as a function of surface reflectance $$ $$R(\mu,\mu_{0},\phi)=R_{0}(\mu,\mu_{0},\phi)+{T\ A_{s}\over 1-s\ A_{s}}\eqno{\hbox{(2)}}$$ $$ where $R_{0}(\mu,\mu_{0},\phi)$ represents the path radiance, $T$ is the transmission function describing the atmospheric effect on upward and downward radiance, $A_{s}$ is the Lambertian reflectance, and $s$ is the spherical albedo of the atmosphere for illumination from below. From this formulation, a set of lookup tables was generated for a variety of sun-sensor geometries to simulate the radiances received by a satellite.

![Figure 4](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-4-source-large.gif)

![Figure 4](/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-4-source-small.gif)

**Figure 4.** - Flowchart for aerosol optical property retrieval over bright surfaces.

An overview of our retrieval algorithm is shown in the dataflow diagram in

Fig. 4. Before the aerosol retrieval processing begins, we first screen out scenes for the presence of clouds. Currently, the Deep Blue algorithm is not retrieving cloud-contaminated pixels. The surface reflectance for a given pixel is then determined for the 412-, 490-, and 670-nm channels from a database based upon its geolocation. The 412-, 490-, and 670-nm radiances are then compared to radiances contained in a lookup table with dimensions consisting of the solar, satellite, and azimuth angles, the surface reflectance, aerosol optical thickness, and single-scattering albedo. A maximum-likelihood method is used to match the appropriate values of aerosol optical thickness and single-scattering albedo to the measured radiances. We provide details for each of these procedures in the sections below.

### A. Cloud Screening

To minimize the cloud contamination problem on our aerosol retrieval, we apply the spatial variance method to the radiance at 412 nm over a 3 ×3 pixels spatial domain. We chose the 412-nm channel because the surface reflectivity at 412 nm is usually darker over land compared to the reflectivity at other longer wavelength channels, allowing more contrast between cloud-free and cloudy pixels. In addition, to distinguish thick dust layers from clouds, we also utilize a computed Deep Blue aerosol index (DAI)<sup>15</sup> defined in a manner similar to the TOMS aerosol index $$ $$\hbox {DAI}=-100\left[\log_{10}\left({I_{412}\over I_{490}}\right)_{\rm meas}-\log_{10}\left({I_{412}\over I_{490}}\right)_{\rm calc}\right]\eqno{\hbox{(3)}}$$ $$ where $I_{\rm meas}$ is the reflectance measured from the satellite and $I_{\rm calc}$ is the reflectance calculated from the lookup tables assuming a Rayleigh scattering atmosphere. The concept of this DAI basically takes advantage of the fact that the spectral dependence of cloud reflectance is flat in the visible spectrum because of very little droplet absorption in this wavelength range. In contrast, there is a strong spectral dependence of dust reflectance, due to extra dust absorption at the shorter visible wavelength, particularly at the blue channels.

The combination of these two procedures has proven reasonably effective in screening out cloudy pixels. However, thin cirrus clouds often appear to be as smooth as aerosol layers and are difficult to separate from aerosols using existing SeaWiFS channels.

For applications to MODIS data on the Terra and Aqua spacecraft, considerable skill in cloud screening is available using the cloud mask algorithm described by Ackerman et al.<sup>1</sup>. This algorithm classifies each pixel as either confident clear, probably clear, probably cloudy, or cloudy, and uses a series of threshold tests applied to 17 of the 36 MODIS bands to identify the presence of clouds in the instrument field-of-view. The specific tests executed are a function of surface type, including land, water, snow/ice, desert, and coastal, and are different during the day and night. Each cloud detection test returns a confidence level that the pixel is clear ranging in value from 1 (high confidence clear) to 0 (low confidence clear). Tests capable of detecting similar cloud conditions are grouped together and a minimum confidence is determined for each group. The final cloud mask is then determined from the product of the results from each group. This approach is clear-sky conservative in the sense that if any test is highly confident that the scene is cloudy, the final clear sky confidence is 0. The first eight bits of the cloud mask provide a summary adequate for many processing applications. Examples of the application of the cloud mask to scenes composed of desert, coastal, and water ecosystems can be found in<sup>23</sup> and<sup>31</sup>.

Over desert regions during the daytime, the cloud mask algorithm makes use of six spectral tests that utilize nine different spectral bands, including the brightness temperature at 13.9 $\mu\hbox {m}$, reflectance threshold at 1.38 $\mu\hbox {m}$, especially sensitive to thin cirrus clouds, and visible threshold and brightness temperature difference tests that help distinguish bright surface features in the visible from heavy aerosol, dust, and clouds.

### B. Surface Reflectivity Database

In order to retrieve aerosol properties, accurate knowledge of the underlying surface reflectance is important, particularly over arid and semiarid regions. The current MODIS aerosol retrieval algorithm over land uses the dark-target approach<sup>18, 19</sup>. It assumes the ratio of surface reflectance between 0.47 $\mu\hbox {m}$ (0.64 $\mu\hbox {m}$) and 2.1 $\mu\hbox {m}$ is 0.25 (0.5). This assumption is valid for most vegetated land surfaces<sup>3</sup>. However, over desert regions, land surface reflectance significantly deviates from this assumption. To obtain the surface reflectance information required by our aerosol retrieval algorithm, we generated a database of surface reflectivity using the minimum reflectivity technique<sup>9, 24</sup>.

We first created a set of lookup tables using a polarized radiative transfer model<sup>4</sup> to simulate the radiances for a range of solar and viewing geometries at the top of the atmosphere that encompass measurements from a satellite. In these calculations we assumed that the radiance was dominated by Rayleigh-scattering and bounded by a Lambertian surface. The Lambert-equivalent reflectivity (LER) is then calculated for each pixel using these lookup tables by matching the surface albedo to the measured satellite radiance. For clear sky conditions (i.e., pure molecular scattering atmosphere), the LER is equivalent to $A_s$ in (2). To minimize cloud contamination problems, we also applied our cloud screening method to this dataset to alleviate the effects of cloud edges on the estimation of the surface albedo.

![Figure 5](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-5-source-large.gif)

![Figure 5](/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-5-source-small.gif)

**Figure 5.** - (Left) Example of a precalculated land surface reflectivity database of $0.1^{\circ}\ \hbox {latitude}\times 0.1^{\circ}\ \hbox {longitude}$ resolution at 412- and 670-nm channels using 1-km SeaWiFS radiances for February 2000. Areas that do not have enough samples to achieve statistical significance due to persistent cloud cover are represented by white color. (Right) Spectral variations of surface reflectivity at six SeaWiFS channels from visible to near-infrared wavelengths for February 2000 (blue diamonds) and June 2000 (red triangles).

![Figure 6](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-6-source-large.gif)

![Figure 6](/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-6-source-small.gif)

**Figure 6.** - Simulated normalized reflectance at 670 nm as a function of viewing angle and aerosol optical thickness for surface reflectances of (a) 0.15, (b) 0.30, (c) 0.40, and (d) 0.50. The aerosol optical thickness is (solid line) 0.0, (dashed line) 0.5, and (chain-dashed line) 1.0. We assumed the single-scattering albedo $\omega_0=1.0$ at 670 nm. The maximum instrumental view angles for both MODIS and SeaWiFS is 55°.

LER values were obtained for six of the SeaWiFS channels (i.e., 412, 443, 490, 510, 670, and 865 nm) and were then sorted into a

$0.1^{\circ}\ \hbox {latitude}\times 0.1^{\circ}\ \hbox {longitude}$

grid for each month of the year. To minimize angular effects due to the surface bidirectional reflectivity on the determination of the surface reflectivity database, we only include samples taken near nadir (i.e., view angle

$<30^{\circ}$). Cloud shadows potentially could also lead to false low reflectance pixels in the satellite measurements, which could result in a surface reflectivity that is too dark. However, longer wavelengths are more susceptible to this problem than shorter wavelength because there is more diffuse light at the shorter wavelength. To mitigate the effects of cloud shadows, the 412-nm surface reflectivity database is obtained first by finding the minimum value of the 412-nm LER for the same grid box within a given month. The databases for other wavelengths are then determined by calculating LER values at each wavelength for the same scene as the one with a minimum value at 412 nm.

![Figure 7](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-7-source-large.gif)

![Figure 7](/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-7-source-small.gif)

**Figure 7.** - Effective phase function of dust particles as a function of scattering angles used in the algorithm, compared to the retrieved values of 670-nm channel from AERONET measurements at Ilorin, Nigeria, and values assuming Mie scattering. For the Mie calculations, the refractive index $(m)=1.55-0.0\ i$. Size parameter $(2\pi r_{0}/\lambda)$ is about 10.

Examples of regional maps of the resulting surface reflectivity database for northern Africa and the Arabian Peninsula at 412 and 670 nm for February 2000 are shown in

Fig. 5

(left). This comparison shows that the 412-nm surface reflectivity is much darker than that at 670 nm. The spectral surface reflectivities from 412–865 nm for the four desert regions indicated by the white boxes in

Fig. 5

(left) are depicted in

Fig. 5

(right). To examine the seasonal variation of the surface reflectivity over the desert, we include in these plots the reflectivity spectra obtained from two different seasons: February (blue diamonds) and June (red triangles). As expected, there is little seasonal variability in the surface albedo of each desert region. Among all the deserts in the Sahara, the Bodele Depression of Chad is the brightest at 412 nm and exhibits a relatively flat spectral shape. This indicates that there is more white-colored material in this region when compared to the other three more reddish-colored deserts in the right panel of

Fig. 5.

As mentioned in the previous section (cf. Fig. 1), when this surface reflectance approaches a critical value, the aerosolinduced modification of the apparent reflectance received by the satellite is negligible. To investigate the limiting reflectance where change in the apparent reflectance caused by aerosol loading is no longer detectable by satellite measurements, we performed radiative transfer simulations using the dust model described in the section below. The results for the 670-nm channel are shown in Fig. 6. Thedifferent lines correspond to different amounts of aerosol loading (solid, dashed, and chain-dashed lines represent the calculations of $\tau_{\rm a}$ values of 0.0, 0.5, and 1.0, respectively). The single-scattering albedo is assumed to be 1.0. For this calculation we also use an “effective” dust phase function described in Fig. 7 in the next section. From these results, we can see that at 670 nm the contribution of dust to the apparent reflectance can be separated from no-aerosol conditions at a surface reflectance of up to 0.30. At 0.40, the contrast between dust-laden and nonaerosol condition diminishes at high view angles. The instrumental view angles for both MODIS and SeaWiFS is up to 55°. This analysis indicates that, assuming no absorption at 670 nm, dust retrievals at this channel can be obtained at a surface reflectance of 0.40 when $\tau_{\rm a}$ is greater than 0.7. Near the dust source regions, $\tau_{\rm a}$ is often observed to exceed this value.

### C. Aerosol Model Selections

The creation of libraries containing realistic aerosol models is the most difficult and critical component in developing a satellite aerosol retrieval algorithm, especially for nonspherical dust particles. Since there are more unknown aerosol parameters than actual pieces of information obtained by the sensor, aerosol retrievals from satellite are an ill-posed inverse problem. In addition, because of the technical complexity in making such measurements, there are few in situ measurements of aerosol scattering and absorption for dust particles from either laboratory or aircraft platforms to form the basis for aerosol models. The reported measured values often vary widely from each other, and the nonspherical shape of aerosols adds even more uncertainty to the aerosol property retrieval due to the unknown angular properties affecting the scattering phase function.

In this study, we created aerosol libraries using values that cover most of the range of the “bulk” properties representative of each aerosol type. We then used these aerosol properties with our radiative transfer model<sup>4</sup> to generate lookup tables used in the aerosol retrievals. The radiative transfer code includes full multiple scattering and takes into account polarization. The neglect of polarization in the radiative transfer code could lead to significant errors in the calculated radiances at 412 and 490 nm for Rayleigh-scattering atmospheres<sup>25</sup>. The parameters used in our aerosol model generation for each aerosol type include aerosol optical thickness, single-scattering albedo, and phase function. In order to save computational time, we divided the globe into several sectors and assumed that mixed aerosols only occur in certain geographic regions. In the following sections, we discuss how our algorithm works under different aerosol conditions.

#### 1. Retrieval for Dust Aerosols

For regions over the Sahara (north of 13°N) and the Arabian Peninsula, we assume that the dominant aerosol type is mineral dust. To account for the effect of

![Figure 8](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-8-source-large.gif)

![Figure 8](/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-8-source-small.gif)

**Figure 8.** - Simulated apparent reflectances as a function of aerosol optical thickness and single-scattering albedo for (top panel) 412- versus 670-nm channel and (bottom panel) 490- versus 670-nm channel. The $\omega_0$ values depicted in the figures are for (top panel) 412 nm and (bottom panel) 490 nm. It is assumed that $\omega_0=1$ at 670 nm. Data from SeaWiFS measurements (denoted by the blue circles) above the Saharan Desert are superimposed on the figure for these observing conditions.

nonspherical dust particle shapes, an “effective phase function” was used in the dust models instead of one calculated by assuming Mie scattering for particle sizes representative of dust aerosols. This “effective phase function” was previously derived empirically to give the best fit of the satellite retrieved

$\tau_{\rm a}$

using our SeaWiFS aerosol algorithm over ocean to the measured

$\tau_{\rm a}$

by the ground-based Aerosol Robotic Network (AERONET) sunphotometer site at Cape Verde. The same set of the “effective phase function” values was also applied to satellite radiances obtained over ocean during ACE-Asia campaign and provides reasonable agreements between our satellite-retrieved

$\tau_{\rm a}$

and measured

$\tau_{\rm a}$

from aircraft and R/V cruise during Asian dust events

<sup>16</sup>.

Fig. 7

is a comparison of the dust “effective phase function” used in our algorithm with that calculated at 670 nm using Mie theory with the refractive index (m) of

$1.55-0.0\ i$

and a log-normal size distribution ($r_{0}=1\ \mu\hbox {m}$,

$\sigma=1.45\ \mu\hbox {m}$). Superimposed are values of the aerosol phase function derived from ground-based AERONET sun and sky measurements (for Ångström exponent

$<$

0.5) using retrievals for nonspherical particles

<sup>5, 6</sup>

at Ilorin, Nigeria, averaged over the month of February 2000. One can see that values of the phase function from our dust model and the AERONET retrievals are larger in the side-scattering direction and are smaller in the backscattering direction, when compared to values calculated assuming Mie scattering from spherical particles.

For estimating single-scattering albedo, a set of values (i.e., 0.87, 0.91, 0.94, 0.96, 0.98, and 1.0) that represent the general range of dust properties was used to generate lookup tables at both 412 and 490 nm. We assume that there is very little absorption for dust particles at 670 nm (i.e., single-scattering albedo $(670\ \hbox {nm})=1.0$)<sup>6</sup>. The Ångström exponent was set to zero for the spectral shape of aerosol optical thickness, and the vertical profile of the aerosol layer was assumed to be a Gaussian distribution with a peak at 3 km and a width of 1 km.

Because the problem of high surface reflectance at 670nm limits the retrieval for medium and low dust loading, as discussed above, the Deep Blue algorithm takes a two-step approach to determine the aerosol properties. For heavy dust loading, the algorithm executes a three-channel technique. Fig. 8 describes the methodology of this three-channel dust retrieval algorithm, in which the relationship of apparent reflectances between two channels is shown as a function of $\tau_{\rm a}$ and $\omega_0$ for 412 versus 670 nm (top panel) and for 490 versus 670 nm (bottom panel). Since we assume a value of zero for the Ångström exponent, the values of $\tau_{\rm a}$ in Fig. 8 are the same for 412, 490, and 670 nm. This assumption is based upon the aerosol climatology using AERONET sun photometer data, which shows that the values of Ångström exponent are generally less than 0.2 for medium to heavy dust loading (i.e., $\tau_{\rm a}>0.5$)<sup>11</sup>. The viewing geometry and surface reflectivity used in these calculations correspond to SeaWiFS measurements taken on February 26, 2000 over the region bounded by the latitudes 18° to 20° N and longitudes 6° to 6.4° E. For single-scattering albedo values ranging from 0.91 to 1.0, the apparent reflectance at 412 and 490 nm increases as $\tau_{\rm a}$ increases for surface reflectivity values derived over this region. The slope between the 412- and 670-nm reflectance also becomes larger as the single-scattering albedo increases. Superimposed on these plots are the corresponding SeaWiFS pixels (denoted by the blue circles) obtained over the region.

For thick dust layers, our algorithm uses the maximum-likelihood method with lookup tables to solve for the values of $\tau_{\rm a}$ and single-scattering albedo at 412 and 490 nm simultaneously, which give the best fit to the satellite measured radiances at these three channels. However, Fig. 6 indicates that for $\tau_{\rm a}$ less than 0.7, the apparent reflectance begins to lose sensitivity to changes in dust loading at 670 nm. For these conditions, we switch to the two-channel approach employing a lookup table technique that is illustrated in Fig. 9. In this figure, apparent reflectances are calculated as a function of aerosol optical thickness and optical property. The values of $\tau_{\rm a}$ are also assumed to be the same for both 412 and 490 nm. This assumption is valid for Ångström exponents less than 0.5, which encompasses most types of dust particles observed near dust sources by AERONET<sup>11</sup>. We use two different aerosols, one with a “whiter” color ($\omega_0=0.98$ and 0.99 at 412 and 490 nm, respectively), and one with a “redder” color ($\omega_0=0.91$ and 0.95 for 412 and 490 nm, respectively). The actual lookup table in the algorithm is composed of radiances for dust models that are chosen to represent variations in the redness of different dust sources. The algorithm basically determines $\tau_{\rm a}$ and the redness of the dust aerosol (i.e., the ratio of “whiter” dust to “redder” dust) simultaneously by matching the measured radiances with those in the table. The single-scattering albedo for the two wavelengths is then derived from this ratio.

![Figure 9](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-9-source-large.gif)

![Figure 9](/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-9-source-small.gif)

**Figure 9.** - Simulated apparent reflectances as a function of aerosol optical thickness for 412- versus 490-nm channel. Two dust types are used, one with “whiter” color ($\omega_0=0.98$ and 0.99 at 412 and 490 nm, respectively), another with “redder” color ($\omega_0=0.91$ and 0.95 at 412 and 490 nm, respectively). The view geometry and surface reflectivities are the same as in Fig. 8.

The procedures to retrieve dust aerosols are summarized as following.

- Step 1)
A two-channel retrieval of $\tau_{\rm a}$ and dust redness using the dust models depicted in Fig. 9.
- Step 2)
If the retrieved $\tau_{\rm a}$ from Step 1) is greater than 0.7, a three-channel retrieval algorithm is applied.

If the retrieved $\tau_{\rm a}$ from Step 1) is less than 0.7, the retrieval will stop and report the retrieved $\tau_{\rm a}$ and $\omega_0$ at 412 and 490 nm.

#### 2. Retrieval for Mixture of Dust/Smoke Aerosols

Every year, during the months of December to February, dust often blows over the Sahel region, mixing with smoke generated from the seasonal biomass burning activity<sup>21</sup>. To retrieve the aerosol properties under the condition of mixed aerosol types found in this region, we assume that the radiance received by the satellite is described by $$ $$R_{\lambda}(\mu,\mu_{o},\phi)=a\ R_{\lambda}^{D}(\mu,\mu_{o},\phi)+(1-a)R_{\lambda}^{S}(\mu,\mu_{o},\phi)\eqno{\hbox{(4)}}$$ $$ where ${R^{D}}_{\lambda}$ and ${R^{S}}_{\lambda}$ are the radiances of the dust and smoke modes, respectively, and $a$ is the ratio of the contributions from the dust and smoke modes to the total radiance. In our algorithm, we use the maximum-likelihood method with our lookup tables to solve for the values of $a$ and aerosol optical thickness at 470 nm that give the best fit to the satellite measured radiances at both 412- and 490-nm channels.

The real and imaginary part of the refractive index at 412 and 490 nm for the aerosol models used in mixed aerosol situations are listed in Table I. For the dust model, we use the dust phase function described above. For the smoke models, we assume spherical particles and a log-normal size distribution with the mode radius $r_{0}=0.14\ \mu\hbox {m}$ and width $\sigma=1.45\ \mu\hbox {m}$.

![Figure](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/36/28498/1273587/1273587-table-1-source-large.gif)

![Figure](/mediastore/IEEE/content/media/36/28498/1273587/1273587-table-1-source-small.gif)

**TABLE I** Table I- Characteristics of Aerosol Properties Used in the Models for DifferentTypes of Aerosols

To investigate the validity of the approach illustrated in (4), we compared the 412-nm radiances to the 490-nm radiances calculated using the aerosol characteristics of the dust and smoke models presented in Table I. The vertical profile of an aerosol layer is assumed to be a Gaussian distribution with a peak at 3km and a width of 1 km. We also compared these two calculated radiances using different mixtures of the two models. From the results, presented in Fig. 10 for two different viewing conditions, it is clear that the radiance ratio from the two channels as a function of aerosol optical thickness is distinctly different between the two aerosol models, meaning that results from these two types of aerosol are easily distinguishable.

![Figure 10](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-10-source-large.gif)

![Figure 10](/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-10-source-small.gif)

**Figure 10.** - Simulated apparent reflectances at 412 and 490 nm as a function of aerosol optical thickness at 470 nm for various mixtures of smoke and dust aerosols. The condition is for $\theta_{0}=24^{\circ}$ when (top panel) $\theta=0^{\circ}$ and (bottom panel) $\theta=42^{\circ}$, $\phi=120^{\circ}$. The surface reflectivity is assumed to be 8% at 412nm and 11% at 490 nm. The properties of smoke and dust aerosol models used in the calculations are listed in Table I.

## Discussion of Uncertainties

### A. Surface Reflectivity

The surface contribution over deserts dominates over the atmospheric contribution when aerosol loading is small. Therefore, the percentage error in the retrieved aerosol optical thickness due to errors in surface reflectance is a function of aerosol optical thickness. Our simulations indicate that for the average surface reflectance value of deserts, an error of 0.01 in surface reflectance $(A_s)$ will result in an error of 20% in aerosol optical thickness $(\tau_{\rm a})$ for $\tau_{\rm a}=1.0$ and $A_s=0.08$. When generating the surface reflectivity database for the aerosol algorithm, we assume that there is no gaseous absorption or aerosol extinction at 412, 490, and 670 nm. According to the AERONET data, the minimum value of $\tau_{\rm a}$ is around 0.05 for sites near dust sources such as Banizoumbou, Niger and Solar Village, Saudi Arabia<sup>11</sup>. The neglect of these background values in $\tau_{\rm a}$ will lead to an overestimate of $A_s$ by 0.0025. Surface bidirectional reflectivity effects will also introduce angular-dependent errors in the retrieved $\tau_{\rm a}$, but it is usually larger in the specular reflection direction. In our current algorithm, we do not perform retrievals over such sun-sensor geometries.

### B. Vertical Aerosol Profile

Sensitivity studies indicate that an error of ±2 km in the altitude of the aerosol plume results in an error in aerosol optical thickness of 25% at 412 nm and 5% at 490 nm. Our previous research indicates a spread of 2 km between the winter (3 km) and summer (5 km) in the altitude of the dust layer over the Saharan Desert, so we believe that this is a reasonable range to expect<sup>13</sup>. This result also indicates that the sensitivity to variations in aerosol height in the retrieved $\tau_{\rm a}$ at 412 nm is much less significant than the technique using UV wavelengths, since the UV retrievals have larger Rayleigh scattering effects.

### C. Particle Shape

Uncertainty in the phase function of dust due to its nonspherical shape is a potentially significant source of error in the retrieved $\tau_{\rm a}$. For the geometries applicable to SeaWiFS and MODIS, the difference between the phase function of spherical particles using Mie theory and randomly oriented spheroids can be as large as 40%<sup>26</sup>. Such differences will lead to large errors in the retrieved $\tau_{\rm a}$. The effect of nonsphericity can be incorporated into the phase function of our dust model using codes that are designed to study such effects<sup>26, 39</sup>, once the shape and aspect ratio of the dust particles are better known.

## Results

We have used the algorithm described above to process radiance data from the SeaWiFS instrument. Fig. 11 shows an example of our results over the Sahara Desert and nearby Arabian Peninsula for four days in February 2000. These days were chosen because ground-based measurements of $\tau_{\rm a}$ were available during this time from an AERONET station located in this region<sup>10</sup>. Our $\tau_{\rm a}$ results were overlaid onto the MODIS “Blue Marble” image (which represents the cloud-free RGB signature of the earth's surface after atmospheric correction). The opacity of the $\tau_{\rm a}$ signal depends on the dust loading; the larger the loading, the more opaque the image.

![Figure 11](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-11-source-large.gif)

![Figure 11](/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-11-source-small.gif)

**Figure 11.** - Example of aerosol optical thickness at 490 nm retrieved from our algorithm over the Sahara Desert and nearby Arabian Peninsula during February 25–28, 2000.

Two types of gaps in the aerosol optical thickness can be seen. The first type is easily identified as the orbital gaps in the coverage of the SeaWiFS instrument. The second type of gap is caused by the presence of clouds. Three instances of such gaps are indicated in Fig. 11. In the first instance, shown on February 27, a fairly large region directly over western Sahara is obscured by clouds. In the other two identified instances, on February 28, the cloud obscuration occurs over much more narrowly focused bands over Mali and Niger. The ability to recognize such cloud obscuration features in these images indicates that the cloud screening procedure used in our algorithm is performing quite well.

Fig. 11 also reveals the evolution of three main dust features in the region during this time period. In the first, a dust storm can be seen developing over the western Sahara. By February 28th, dust from this storm flowed off the coast of Mauritania out over the Atlantic and curled back toward the western coast of the Iberian Peninsula. In the second, a small, dense plume of dust developed in the low-lying region where the borders of Mali, Niger, and Algeria meet. The dust was prevented from flowing outward by the higher level terrain bounding it on the west, north, and east. Finally, dust from the Bodele Depression north of Lake Chad picked up intensity from February 25–28. This depression, which contains the fine-grain dust indicative of a dry-lake bed, provides a consistent source of such dust during most of the year.

Examples of the retrieved single-scattering albedo at 412 and 490 nm are shown in Fig. 12 for two different dust plumes. One plume (15° to 18° N; 17° to 17.4° E) is downwind of the Bodele depression, and another (18° to 20° N; 6°to 6.4° E) originates from the Algeria/Niger border region. The dust properties from these two sources clearly show distinctly different characteristics. The Bodele depression plume seems to be brighter (higher reflectance) and whiter (flatten spectral dependence), compared to the Algeria/Niger plume.

![Figure 12](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-12-source-large.gif)

![Figure 12](/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-12-source-small.gif)

**Figure 12.** - Example of single-scattering albedo at 412 and 490 nm retrieved from our algorithm over the region about 100 km downwind of the Bodele depression on February 2, 2000, and downwind of the Algeria/Niger source on February 26, 2000. The vertical bars represent the standard deviation of the retrieved values within the selected box.

### A. Comparisons to Ground-Based Data

![Figure 13](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-13-source-large.gif)

![Figure 13](/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-13-source-small.gif)

**Figure 13.** - Comparison of satellite-derived $\tau_{\rm a}$ values for February 2000 with those from the AERONET sunphotometer located at Ilorin, Nigeria. (Dashed line) Represent the 20% differences. (Two outer solid lines) Represents 30% differences.

![Figure 14](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-14-source-large.gif)

![Figure 14](/mediastore/IEEE/content/media/36/28498/1273587/1273587-fig-14-source-small.gif)

**Figure 14.** - Comparison of satellite-derived $\tau_{\rm a}$ values for June–July 2000 with those from the AERONET sunphotometer located at Solar Village, Saudi Arabia. (Dashed line) Represent the 20% differences. (Two outer solid lines) Represents 30% differences.

As previously stated, ground-based

$\tau_{\rm a}$

results for a sunphotometer ground station based in Ilorin, Nigeria, are available during February 2000. In

Fig. 13, we compare results of our

$\tau_{\rm a}$

retrieval over Ilorin with ground-based measurements of

$\tau_{\rm a}$

from the AERONET sunphotometer. The comparisons show that our retrievals are consistently within 20% of the sunphotometer

$\tau_{\rm a}$

measurements. During the dry season, this site is often under the influence of both Saharan dust and smoke from biomass burning activities.

To investigate seasonal effects and dust properties over a different region, we also compared our $\tau_{\rm a}$ retrievals to sunphotometer measurements taken over Solar Village, Saudi Arabia, in June and July 2000. This comparison, shown in Fig. 14, also indicates that our retrievals are generally within 20% of those from sunphotometer measurements.

## Conclusion

Satellite imagery over desert areas indicate that aerosol-induced modifications in the signal received by satellites at wavelengths longer than 600 nm can only be detected for thick dust plumes. These red wavelengths were commonly used in previous aerosol retrieval algorithms for instruments such as the Advanced Very High Resolution Radiometer onboard the Polar-orbiting Operational Environmental Satellite (POES) system. To extend satellite retrievals to thin and moderate dust plumes, we propose a new approach to retrieve aerosols over bright surfaces by taking advantage of the darker properties of such surfaces at the blue channels (i.e., 412 and 490 nm for SeaWiFS; 412 and 470 nm for MODIS). Using these shorter wavelength channels, the presence of aerosols can be determined from satellite data at a much lower aerosol loading compared to retrievals that use red channels, provided the radiance level does not saturate the sensor gain. However, there is a tradeoff between using the blue (i.e., 412 and 490 nm) channels and using the red (i.e., 670 nm) channel. Although the desert surfaces are darker at the blue channels, the variability of dust optical properties for these channels is larger than that for the red channel since there is little absorption of dust at 670 nm. Because of this tradeoff, the optimal retrieval of aerosol optical thickness and spectral single-scattering albedo can only be achieved by using information from all three channels (412, 490, and 670 nm) obtained over those pixels that contain thick layers of dust in the atmosphere $(\tau_{\rm a}>0.7)$.

Analyses of results using the new algorithm show that dust plumes from some sources (e.g., Bodele depression) absorb less solar radiation than those from other sources (e.g., those in Algeria/Niger). Information such as this resulting from the application of our algorithm will help reduce the uncertainty in the determination of radiative forcing due to mineral dust near source regions using a previously developed approach<sup>14</sup>. This technique can be applied to aerosol retrievals over bright surfaces such as arid, semiarid, urban, and sparsely vegetated surfaces. It can also be applied to any future satellite instruments that have similar features as MODIS or SeaWiFS. The National Polar-orbiting Operational Environmental Satellite System (NPOESS) program plans to launch a series of missions that include the Visible/Infrared Imager/Radiometer Suite (VIIRS). VIIRS is currently under development for NPOESS and will measure radiances at multiple channels, including 412, 490, and 670 nm.

With the launch of the first VIIRS sensors scheduled in late 2006 onboard the NPOESS Preparatory Project (NPP) satellite and future launches scheduled well into the next decade on the NPOESS series of satellites, the Deep Blue algorithm will be able to provide an invaluable long-term record of aerosol information over bright surfaces for use in climate studies.

## ACKNOWLEDGMENT

The authors are grateful to O. Dubovik for providing scattering phase function of nonspherical dust particle retrieved from AERONET sun/sky measurements for comparison with our values and to E. G. Moody for assisting with the MODIS surface reflectance database. They also thank B. N. Holben and R. Pinker for their effort in establishing and maintaining the AERONET sites at Solar Village, Saudi Arabia and Ilorin, Nigeria for providing aerosol optical thickness observations.

## References (39 total, showing 39)

1. S. A. Ackerman, K. I. Strabala, W. P. Menzel, R. A. Frey, C. C. Moeller and L. E. Gumley, “Discriminating clear sky from clouds with MODIS,” J. Geophys. Res. , pp. 32 141–32 157, vol. 103, 1998.
2. R. A. Barnes, R. E. Eplee, G. M. Schmidt, F. S. Patt and C. R. McClain, “Calibration of SeaWiFS. I. Direct techniques,” Appl. Opt. , pp. 6682–6700, vol. 40, 2001.
3. D. A. Chu, Y. J. Kaufman, J.-D. Chern, J.-M. Mao, C. Li and B. N. Holben, “Global monitoring of air pollution over land from EOS-Terra MODIS,” J. Geophys. Res. , DOI: 10.1029/2002JD003179 p. 4661, vol. 108, 2003.
4. J. V. Dave, Development of programs for computing characteristics of ultraviolet radiation, IBM Corp., Fed. Syst. Div. Gaithersburg, MD , Tech. Rep. 1972.
5. O. Dubovik, B. N. Holben, T. Lapyonok, A. Sinyuk, M. I. Mishchenko, P. Yang and I. Slutsker, “Non-spherical aerosol retrieval method employing light scattering by spheroids,” Geophys. Res. Lett. , pp. 54-1–54-4, vol. 29, 2002.
6. O. Dubovik, B. N. Holben, T. F. Eck, A. Smirnov, Y. J. Kaufman, M. D. King, D. Tanré and I. Slutsker, “Variability of absorption and optical properties of key aerosol types observed in worldwide locations,” J. Atmos. Sci. , pp. 590–608, vol. 59, 2002.
7. J. Haywood and O. Bougher, “Estimates of the direct and indirect radiative forcing due to tropospheric aerosols: A review,” Rev. Geophys. , pp. 513–543, vol. 38, 2000.
8. J. R. Herman, P. K. Bhartia, O. Torres, N. C. Hsu, C. J. Seftor and E. Celarier, “Global distribution of UV-absorbing aerosols from Nimbus-7/TOMS data,” J. Geophys. Res. , pp. 16 911–16 922, vol. 102, 1997.
9. J. R. Herman and E. A. Celarier, “Earth surface reflectivity climatology at 340–380 nm from TOMS data,” J. Geophys. Res. , pp. 28 003–28 011, vol. 102, 1997.
10. B. N. Holben, T. F. Eck, I. Slutsker, D. Tanre, J. P. Buis, A. Setzer, E. Vermote, J. A. Reagan, Y. Kaufman, T. Nakajima, F. Lavenu, I. Jankowiak and A. Smirnov, “AERONET—A federated instrument network and data archive for aerosol characterization,” Remote Sens. Environ. , pp. 1–16, vol. 66, 1998.
11. B. N. Holben, D. Tanre, A. Smirnov, T. F. Eck, I. Slutsker, N. Abuhassan, W. W. Newcomb, J. Schafer, B. Chatenet, F. Lavenue, Y. J. Kaufman, J. V. J. Vande Castle, A. Setzer, B. Markham, D. Clark, R. Frouin, R. Halthore, A. Karnieli, N. T. O'Neill, C. Pietras, R. T. Pinker, K. Voss and G. Zibordi, “An emerging ground-based aerosol climatology: Aerosol optical depth from AERONET,” J. Geophys. Res. , pp. 12 067–12 097, vol. 106, 2001.
12. N. C. Hsu, J. R. Herman, P. K. Bhartia, C. J. Seftor, O. Torres, A. M. Thompson, J. F. Gleason, T. F. Eck and B. N. Holben, “Detection of biomass burning smoke from TOMS measurements,” Geophys. Res. Lett. , pp. 745–748, vol. 23, 1996.
13. N. C. Hsu, J. R. Herman, O. Torres, B. N. Holben, D. Tanré, T. F. Eck, A. Smirnov, B. Chatenet and F. Lavenu, “Comparisons of the TOMS aerosol index with sun-photometer aerosol optical thickness: Results and applications,” J. Geophys. Res. , pp. 6269–6279, vol. 104, 1999.
14. N. C. Hsu, J. R. Herman and C. Weaver, “Determination of radiative forcing of Saharan dust using combined TOMS and ERBE data,” J. Geophys. Res. , pp. 20 649–20 661, vol. 105, 2000.
15. N. C. Hsu, W. D. Robinson, S. W. Bailey and P. J. Werdell, The description of the SeaWiFS absorbing aerosol index, Goddard Space Flight Center Greenbelt, MD, SeaWiFS NASA Tech. Memo. 2000-206 892 pp. 3–5, vol. 10, 2000.
16. N. C. Hsu, S. C. Tsay, B. Schmid, J. Redemann, J. Livingston, P. Russell, R. Frouin, B. Holben and K. Knobelspiesse, “Satellite retrieval of aerosol properties over ocean during ACE-Asia using an improved SeaWiFS aerosol algorithm,” J. Geophys. Res. , 2004.
17. Y. J. Kaufman, “Satellite sensing of aerosol absorption,” J. Geophys. Res. , pp. 4307–4317, vol. 92, 1987.
18. Y. J. Kaufman, D. Tanré, L. A. Remer, E. F. Vermote, D. A. Chu and B. N. Holben, “Remote sensing of tropospheric aerosol from EOS-MODIS over the land using dark targets and dynamic aerosol models,” J. Geophys. Res. , pp. 17 051–17 067, vol. 102, 1997.
19. Y. J. Kaufman, A. Wald, L. A. Remer, B. C. Gao, R. R. Li and L. Flynn, “Remote sensing of aerosol over the continents with the aid of a 2.2 \$\mu\hbox {m}\$ channel,” IEEE Trans. Geosci. Remote Sensing , pp. 1286–1298, vol. 35, Sept. 1997.
20. Y. J. Kaufman, A. Karnieli and D. Tanré, “Detection of dust over deserts using satellite data in the solar wavelengths,” IEEE Trans. Geosci. Remote Sensing , pp. 525–531, vol. 38, Jan. 2000.
21. Y. J. Kaufman, D. Tanré and O. Boucher, “A satellite view of aerosols in the climate system,” Nature , pp. 215–223, vol. 419, 2002.
22. M. D. King, Y. J. Kaufman, D. Tanré and T. Nakajima, “Remote sensing of tropospheric aerosols from space: Past, present and future,” Bull. Amer. Meteorol. Soc. , pp. 2229–2259, vol. 80, 1999.
23. M. D. King, W. P. Menzel, Y. J. Kaufman, D. Tanré, B. C. Gao, S. Platnick, S. A. Ackerman, L. A. Remer, R. Pincus and P. A. Hubanks, “Cloud and aerosol properties, precipitable water, and profiles of temperature and water vapor from MODIS,” IEEE Trans. Geosci. Remote Sensing , pp. 442–458, vol. 41, Feb. 2003.
24. R. B. A. Koelemeijer, J. F. de Haan and P. Stammes, “A database of spectral surface reflectivity in the range 335–772 nm derived from 5.5 years of GOME observations,” J. Geophys. Res. , DOI: 10.1029/2002JD002429 p. 4070, vol. 108, 2003.
25. M. I. Mishchenko, A. A. Lacis and L. D. Travis, “Errors introduced by the neglect of polarization in radiance calculations for Rayleigh scattering atmospheres,” J. Quant. Spectrosc. Radiat. Transf. , pp. 491–510, vol. 51, 1994.
26. M. I. Mishchenko, L. D. Travis, R. A. Kahn and R. A. West, “Modeling phase functions for dustlike tropospheric aerosols using a shape mixture of polydisperse spheroids,” J. Geophys. Res. , pp. 16 831–16 847, vol. 102, 1997.
27. M. I. Mishchenko, I. V. Geogdzhayev, B. Cairns, W. B. Rossow and A. A. Lacis, “Aerosol retrievals over the ocean by use of channels 1 and 2 AVHRR data: Sensitivity analysis and preliminary results,” Appl. Opt. , pp. 7325–7341, vol. 38, 1999.
28. E. Moody, M. D. King, S. Platnick, C. B. Schaaf and F. Gao, “Spatially complete surface albedo data sets: Value-added products derived from Terra MODIS land products,” EOS Trans. AGU, Fall Meeting Suppl., Abstract B22E-03, vol. 84, 2003.
29. G. Myhre and F. Stordal, “Global sensitivity experiments of the radiative forcing due to mineral aerosols,” J. Geophys. Res. , pp. 18 193–18 204, vol. 106, 2001.
30. T. Nakajima and A. Higurashi, “A use of two-channel radiances for an aerosol characterization from space,” Geophys. Res. Lett. , pp. 3815–3818, vol. 25, 1998.
31. S. Platnick, M. D. King, S. A. Ackerman, W. P. Menzel, B. A. Baum, J. C. Riédi and R. A. Frey, “The MODIS cloud products: Algorithms and examples from Terra,” IEEE Trans. Geosci. Remote Sensing , pp. 459–473, vol. 41, Feb. 2003.
32. C. B. Schaaf, F. Gao, A. H. Strahler, W. Lucht, X. W. Li, T. Tsang, N. C. Strugnell, X. Y. Zhang, Y. F. Jin, J. P. Muller, P. Lewis, M. Barnsley, P. Hobson, M. Disney, G. Roberts, M. Dunderdale, C. Doll, R. P. d'Entremont, B. X. Hu, S. L. Liang, J. L. Privette and D. Roy, “First operational BRDF, albedo nadir reflectance products from MODIS,” Remote Sens. Environ. , pp. 135–148, vol. 83, 2002.
33. I. N. Sokolik and O. B. Toon, “Direct radiative forcing by anthropogenic airborne mineral aerosols,” Nature , pp. 681–683, vol. 381, 1996.
34. L. L. Stowe, A. M. Ignatov and R. R. Singh, “Development, validation, and potential enhancements to the second generation operational aerosol product at the National Oceanic and Atmospheric Administration,” J. Geophys. Res. , pp. 16 923–16 934, vol. 102, 1997.
35. D. Tanré and M. Legrand, “On the satellite retrieval of Saharan dust optical thickness over land: Two different approaches,” J. Geophys. Res. , pp. 5221–5227, vol. 96, 1991.
36. D. Tanré, E. F. Vermote, B. N. Holben and Y. J. Kaufman, “Satellite aerosol retrieval over land surfaces using the structure functions,” Proc. IGARSS, pp. 1474–1477, vol. 2, 1992.
37. D. Tanré, Y. J. Kaufman, M. Herman and S. Mattoo, “Remote sensing of aerosol over oceans from EOS-MODIS,” J. Geophys. Res. , pp. 16 971–16 988, vol. 102, 1997.
38. O. Torres, P. K. Bhartia, J. R. Herman, Z. Ahmad and J. Gleason, “Derivation of aerosol properties from satellite measurements of backscattered ultraviolet radiation. Theoretical basis,” J. Geophys. Res. , pp. 17 099–17 110, vol. 103, 1998.
39. P. Yang, K. N. Liou, M. I. Mishchenko and B.-G. Gao, “Efficient finite-difference time-domain scheme for light scattering by dielectric particles: Application to aerosols,” Appl. Opt. , pp. 3727–3737, vol. 39, 2000.
