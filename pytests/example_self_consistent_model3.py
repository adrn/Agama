#!/usr/bin/python
"""
Example of construction of a three-component disk-bulge-halo equilibrium model of a galaxy.
The approach is explained in example_self_consistent_model.py;
this example differs in that it has a somewhat simpler structure (only a single stellar disk
component, no stellar halo or gas disk).
Another modification is that the halo and the bulge are represented by 'pseudo-isotropic' DF:
it is a spherical isotropic DF that is constructed using the Eddington inversion formula
for the given density profile in the spherically-symmetric approximation of the total potential.
This DF is then expressed in terms of actions and embedded into the 'real', non-spherical
potential, giving rise to a slightly different density profile; however, it is close enough
to the input one so that only one iteration is performed at the first stage.
Then the disk DF is constructed in the current total potential, and a few more iterations
are needed to converge towards a self-consistent model.
"""

import agama, numpy, ConfigParser, os, sys

# write out the rotation curve for the entire model (not split by components)
def writeRotationCurve(filename, potential):
    potential.export(filename)
    radii = numpy.logspace(-2, 1.5, 71)
    vcirc = (-potential.force( numpy.vstack((radii, radii*0, radii*0)).T)[:,0] * radii)**0.5
    numpy.savetxt(filename, numpy.vstack((radii, vcirc)).T, fmt="%.6g", header="radius\tv_circ")

# print some diagnostic information after each iteration
def printoutInfo(model, iteration):
    densDisk = model.components[0].getDensity()
    densBulge= model.components[1].getDensity()
    densHalo = model.components[2].getDensity()
    print \
        "Disk  total mass=%g," % densDisk.totalMass(), \
        "rho(R=2,z=0)=%g, rho(R=2,z=0.25)=%g" % \
        (densDisk.density(2, 0, 0), densDisk.density(2, 0, 0.25))
    print \
        "Bulge total mass=%g," % densBulge.totalMass(), \
        "rho(R=0.4,z=0)=%g" % \
        (densBulge.density(0.4, 0, 0))
    print \
        "Halo  total mass=%g," % densHalo.totalMass(), \
        "rho(R=2,z=0)=%g, rho(R=0,z=2)=%g" % \
        (densHalo.density(2, 0, 0), densHalo.density(0, 0, 2))
    print "Potential at origin=-(%g)^2," % (-model.potential.potential(0,0,0))**0.5, \
        "total mass=%g" % model.potential.totalMass()
    densDisk. export("dens_disk_iter" +str(iteration));
    densBulge.export("dens_bulge_iter"+str(iteration));
    densHalo. export("dens_halo_iter" +str(iteration));
    writeRotationCurve("rotcurve_iter"+str(iteration), model.potential)

if __name__ == "__main__":
    # read parameters from the INI file
    iniFileName = os.path.dirname(os.path.realpath(sys.argv[0])) + "/../data/SCM3.ini"
    ini = ConfigParser.RawConfigParser()
    ini.read(iniFileName)
    iniPotenHalo  = dict(ini.items("Potential halo"))
    iniPotenBulge = dict(ini.items("Potential bulge"))
    iniPotenDisk  = dict(ini.items("Potential disk"))
    iniDFDisk     = dict(ini.items("DF disk"))
    iniSCMHalo    = dict(ini.items("SelfConsistentModel halo"))
    iniSCMBulge   = dict(ini.items("SelfConsistentModel bulge"))
    iniSCMDisk    = dict(ini.items("SelfConsistentModel disk"))
    iniSCM        = dict(ini.items("SelfConsistentModel"))

    # initialize the SelfConsistentModel object (only the potential expansion parameters)
    model = agama.SelfConsistentModel(**iniSCM)

    # create initial density profiles of all components
    densityDisk  = agama.Density(**iniPotenDisk)
    densityBulge = agama.Density(**iniPotenBulge)
    densityHalo  = agama.Density(**iniPotenHalo)

    # add components to SCM - at first, all of them are static density profiles
    model.components.append(agama.Component(density=densityDisk,  disklike=True))
    model.components.append(agama.Component(density=densityBulge, disklike=False))
    model.components.append(agama.Component(density=densityHalo,  disklike=False))

    # compute the initial potential
    model.iterate()
    writeRotationCurve("rotcurve_init", model.potential)

    # construct the DF of the disk component, using the initial (non-spherical) potential
    dfDisk  = agama.DistributionFunction(potential=model.potential, **iniDFDisk)
    # initialize the DFs of spheroidal components using the Eddington inversion formula
    # for their respective density profiles in the spherically-symmetric initial guess for the potential
    pot_sph = agama.Potential(type='Multipole', density=model.potential, lmax=0, gridsizer=100, rmin=1e-3, rmax=1e3)
    dfBulge = agama.DistributionFunction(type='PseudoIsotropic', potential=pot_sph, density=densityBulge)
    dfHalo  = agama.DistributionFunction(type='PseudoIsotropic', potential=pot_sph, density=densityHalo)

    print "\033[1;33m**** STARTING ITERATIVE MODELLING ****\033[0m\nMasses (computed from DF): ", \
        "Mdisk=%g,"  % dfDisk.totalMass(), \
        "Mbulge=%g," % dfBulge.totalMass(), \
        "Mhalo=%g"   % dfHalo.totalMass()
    printoutInfo(model, 0)

    # replace the initially static SCM components with the DF-based ones
    model.components[0] = agama.Component(df=dfDisk,  disklike=True,  **iniSCMDisk)
    model.components[1] = agama.Component(df=dfBulge, disklike=False, **iniSCMBulge)
    model.components[2] = agama.Component(df=dfHalo,  disklike=False, **iniSCMHalo)

    # do a few more iterations to obtain the self-consistent density profile for both disks
    for iteration in range(6):
        print "\033[1;37mStarting iteration #%d\033[0m" % iteration
        model.iterate()
        printoutInfo(model, iteration)

    print "\033[1;33mComputing disk density and velocity profiles\033[0m"
    # take only the disk component
    modelDisk = agama.GalaxyModel(potential=model.potential, df=dfDisk, af=model.af)
    # radial grid for computing various quantities in the disk plane
    Rdisk = float(iniPotenDisk["scaleradius"])
    Hdisk = float(iniPotenDisk["scaleheight"])
    R = agama.nonuniformGrid(48, 0.01*Rdisk, 10.0*Rdisk)
    xyz = numpy.column_stack((R, R*0, R*0))
    Sigma,_ = modelDisk.projectedMoments(R)
    rho,vmean,sigma = modelDisk.moments(xyz, vel=True)
    force, deriv = model.potential.forceDeriv(xyz)
    kappa = numpy.sqrt(-deriv[:,0] - 3*force[:,0]/R)
    ToomreQ = sigma[:,0]**0.5 * kappa / 3.36 / Sigma
    numpy.savetxt("disk_plane",
        numpy.vstack((R, Sigma, rho, sigma[:,0]**0.5, sigma[:,1]**0.5,
        (sigma[:,2]-vmean[:,2]**2)**0.5, vmean[:,2], (-R*force[:,0])**0.5, ToomreQ)).T,
        header="R Sigma rho(R,z=0) sigma_R sigma_z sigma_phi v_phi,mean v_circ ToomreQ", fmt="%.6g")

    # export model to an N-body snapshot
    print "\033[1;33mCreating an N-body representation of the model\033[0m"
    format = 'text'  # one could also use 'nemo' or 'gadget' here

    # first create a representation of density profiles without velocities
    # (just for demonstration), by drawing samples from the density distribution
    print "Sampling disk density"
    agama.writeSnapshot("dens_disk_final",  model.components[0].getDensity().sample(160000), format)
    print "Sampling bulge density"
    agama.writeSnapshot("dens_bulge_final", model.components[1].getDensity().sample(40000), format)
    print "Sampling halo density"
    agama.writeSnapshot("dens_halo_final",  model.components[2].getDensity().sample(800000), format)

    # now create genuinely self-consistent models of both components,
    # by drawing positions and velocities from the DF in the given (self-consistent) potential
    print "Sampling disk DF"
    agama.writeSnapshot("model_disk_final", \
        agama.GalaxyModel(potential=model.potential, df=dfDisk,  af=model.af).sample(160000), format)
    print "Sampling bulge DF"
    agama.writeSnapshot("model_bulge_final", \
        agama.GalaxyModel(potential=model.potential, df=dfBulge, af=model.af).sample(40000), format)
    print "Sampling halo DF"
    agama.writeSnapshot("model_halo_final", \
        agama.GalaxyModel(potential=model.potential, df=dfHalo,  af=model.af).sample(800000), format)
