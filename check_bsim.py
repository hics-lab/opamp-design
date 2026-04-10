import math

# ETRI NMOS parameters
P = dict(
    VTH0=0.6853721, K1=0.7161694, K2=-4.636134e-5, K3=30, K3B=-10,
    W0=8.4822e-6, NLX=2.605385e-7, DVT0W=0, DVT1W=0, DVT2W=-0.032,
    DVT0=1.1124703, DVT1=0.2497294, DVT2=0,
    U0=503.2726356, UA=1e-11, UB=2.436791e-18, UC=8.083776e-11,
    VSAT=8.511705e4, A0=0.6441421, AGS=0.1378118, B0=1.24596e-8, B1=-1.01e-7,
    KETA=-7.464619e-3, A1=0, A2=1,
    RDSW=1.19434e3, PRWG=-0.01, PRWB=8.389165e-3, WR=1,
    WINT=1.513015e-7, LINT=2.156876e-8, XL=0, XW=-1e-7,
    VOFF=-0.0998905, NFACTOR=1.1, CIT=0, CDSC=4.327068e-4, CDSCD=0,
    CDSCB=4.5945e-4, ETA0=1.109281e-3, ETAB=-0.2,
    DSUB=0.8836863, PCLM=0.6857613, PDIBLC1=0.0466939, PDIBLC2=5e-4,
    PDIBLCB=0, DROUT=0.2761545, PSCBE1=4.495624e8, PSCBE2=5.004804e-5,
    PVAG=0, DELTA=1e-3, TOX=1.05e-8, XJ=2.7e-7, NCH=2.4e17, MOBMOD=1
)

_eox = 3.453e-11  # F/m
_esi = 1.044e-10
_ni  = 1.45e10 * 1e6  # /m³
_q   = 1.602e-19
_Vtm = 0.02585

def bsim3Ids(P, W, L, Vgs, Vds, Vbs):
    if Vds < 0: Vds = 0
    if Vgs < -0.5: Vgs = -0.5

    Leff = max(L - 2*P['LINT'] + P['XL'], 1e-8)
    Weff = max(W - 2*P['WINT'] + P['XW'], 1e-8)
    Cox = _eox / P['TOX']
    Vtm = _Vtm

    NDEP = P['NCH']
    PHIs = 2*Vtm*math.log(max(NDEP/_ni, 1))
    sqPHIs = math.sqrt(max(PHIs, 0.01))

    lt = math.sqrt(_esi/_eox * P['TOX'] * P['XJ'])
    dvt1l = P['DVT1']*Leff/(2*lt)
    coshTerm = 0 if dvt1l>40 else 2/(math.exp(dvt1l)+math.exp(-dvt1l))
    dVth_sce = -P['DVT0']*2*Vtm*coshTerm

    sqPHIsVbs = math.sqrt(max(PHIs-Vbs, 1e-6))
    dVth_body = P['K1']*(sqPHIsVbs - sqPHIs) + P['K2']*Vbs
    # ETAB*Vbs 양수이면 DIBL 비정상 증가 → 0으로 클램핑
    dVth_dibl = -(P['ETA0'] + min(P['ETAB']*Vbs, 0))*Vds
    dVth_nlx = -2*Vtm*P['NLX']/Leff if (P['NLX']>0 and Leff>0) else 0

    Vth = P['VTH0'] + dVth_body + dVth_sce + dVth_dibl + dVth_nlx

    Cdsc = P['CDSC'] + P['CDSCD']*Vds + P['CDSCB']*Vbs
    n = max(1 + P['K1']/(2*sqPHIsVbs) + Cdsc/Cox + P['DSUB']*coshTerm, 1.0)

    Vgst = Vgs - Vth
    x = Vgst/(2*n*Vtm)
    if x>40: Vgsteff=Vgst
    elif x<-40: Vgsteff=2*n*Vtm*math.exp(x)
    else: Vgsteff=2*n*Vtm*math.log(1+math.exp(x))
    Vgsteff = max(Vgsteff, 1e-12)

    Eeff = Vgsteff/P['TOX']
    denom = 1 + P['UA']*Eeff + P['UB']*Eeff**2
    if P['MOBMOD']==1: denom += P['UC']*Vbs*Eeff
    Ueff = P['U0']/max(denom, 0.01)

    Esat = 2*P['VSAT']*100/(Ueff+1e-10)   # V/cm
    EsatL = Esat*Leff*100                  # V

    Abulk0 = 1 + P['A0']*(1-math.exp(-Leff*1e6/0.5))/(Leff*1e6+1e-6)
    Abulk = max(Abulk0*(1+P['KETA']*Vbs), 0.1)

    Vdsat = Vgsteff*EsatL/(Abulk*Vgsteff+EsatL+1e-20)

    delta4 = P['DELTA']
    diff = Vdsat - Vds - delta4
    Vdseff = Vdsat - 0.5*(diff + math.sqrt(diff**2 + 4*delta4*Vdsat))

    beta = (Ueff*1e-4)*Cox*Weff/Leff
    fac = 1 + Vdseff/EsatL
    Ids0 = beta*((Vgsteff - Abulk*Vdseff*0.5)*Vdseff)/max(fac, 0.01)

    Leff_cm = Leff*1e2
    diffsat = max(Vds-Vdsat, 1e-6)

    VaCLM = 1e6
    if P['PCLM']>0 and diffsat>1e-6:
        litl = math.sqrt(max(3*P['TOX']*P['XJ'], 1e-20))
        litl_cm = litl*1e2
        logArg = 1 + diffsat/(litl_cm*Esat+1e-20)
        lnVal = max(math.log(logArg), 1e-10)
        VaCLM = diffsat*Leff_cm/(P['PCLM']*litl_cm*lnVal)

    VaDIBL = 1e6
    droutExp = math.exp(-min(P['DROUT']*Leff/(2*lt), 40))
    thetaR = P['PDIBLC1']*droutExp + P['PDIBLC2']
    if thetaR>1e-10: VaDIBL = Vgsteff/thetaR

    VaSCBE = 1e6
    if P['PSCBE1']>0 and diffsat>0.01:
        expArg = min(P['PSCBE2']*Leff_cm/diffsat, 40)
        VaSCBE = P['PSCBE1']*Leff_cm*math.exp(-expArg)/max(diffsat, 1e-4)

    Va = 1/(1/VaCLM + 1/VaDIBL + 1/VaSCBE)
    Ids = max(Ids0*(1+diffsat/max(Va, 1e-3)), 0)
    return Ids, Vth, Vgsteff, Vdsat, Ids0, VaCLM, VaDIBL

# LTspice 결과: Vicm=1.65V → Vout=3.539V, Vp=0.549V
# M1: Vgs=Vicm-Vp=1.101V, Vds=Vout-Vp=2.990V, Vbs=VSS-Vp=-0.549V (body=VSS, src=Vp)
# M5: Vgs=Vb-0=0.93V, Vds=Vp-0=0.549V, Vbs=0 (body=VSS=src)
# M3: Vgs=VDD-Vout=1.461V(VSG), Vds=VDD-Vout=1.461V(VSD), Vbs=0(VSB=src=VDD=body)

Vp_lt = 0.549   # LTspice tail voltage
print("=== M1 (NMOS, W=20u, L=1u) ===")
print(f"Vgs=1.101V, Vds=2.990V, Vbs={-Vp_lt:.3f}V  (body=VSS=0, source=Vp={Vp_lt}V)")
I1,Vth,Vgsteff,Vdsat,Ids0,VaCLM,VaDIBL = bsim3Ids(P, 20e-6, 1e-6, 1.101, 2.990, -Vp_lt)
print(f"  Vth={Vth:.4f}V, Vgsteff={Vgsteff:.4f}V, Vdsat={Vdsat:.4f}V")
print(f"  VaCLM={VaCLM:.3f}V, VaDIBL={VaDIBL:.3f}V")
print(f"  Ids0={Ids0*1e6:.2f}uA, Ids={I1*1e6:.2f}uA")

print("\n=== M5 (NMOS, W=40u, L=1u) ===")
print("Vgs=0.93V, Vds=0.549V, Vbs=0")
I5,Vth5,Vgsteff5,Vdsat5,Ids05,_,_ = bsim3Ids(P, 40e-6, 1e-6, 0.93, 0.549, 0)
print(f"  Vth={Vth5:.4f}V, Vgsteff={Vgsteff5:.4f}V, Vdsat={Vdsat5:.4f}V")
print(f"  Ids={I5*1e6:.2f}uA")
print(f"  KCL check: 2*I1={2*I1*1e6:.2f}uA vs I5={I5*1e6:.2f}uA")

print("\n=== 동작점 일관성 ===")
print(f"  2*I1 - I5 = {(2*I1-I5)*1e6:.3f} uA  (→ 0이어야 함)")

# 이번엔 Vout 탐색: M3/M4 전류와 M1 전류 균형
# PMOS params
PP = dict(
    VTH0=0.955701, K1=0.506553, K2=0, K3=22.729, K3B=-6.08389,
    W0=1.69386e-6, NLX=1.9959e-7, DVT0W=0, DVT1W=0, DVT2W=-0.032,
    DVT0=3.50997, DVT1=0.727088, DVT2=-0.0183815,
    U0=266.196, UA=3.69133e-9, UB=1e-21, UC=-3.87597e-11,
    VSAT=9.55069e4, A0=0.623211, AGS=0.194947, B0=3.06684e-7, B1=1e-7,
    KETA=-4.28948e-3, A1=3.86287e-4, A2=0.9,
    RDSW=3.60374e3, PRWG=-0.0799373, PRWB=0.0411799, WR=1,
    WINT=1.36348e-7, LINT=6.23443e-9, XL=0, XW=-1e-7,
    VOFF=-0.134374, NFACTOR=1.87019, CIT=0, CDSC=6.79352e-4, CDSCD=0,
    CDSCB=1.06434e-3, ETA0=0.0463143, ETAB=0, DSUB=0.338036,
    PCLM=1.53691, PDIBLC1=0, PDIBLC2=4.5e-4, PDIBLCB=0, DROUT=1.79767,
    PSCBE1=8e8, PSCBE2=7e-9, PVAG=-0.29474, DELTA=7.07618e-3,
    TOX=1.05e-8, XJ=2.2e-7, NCH=5e16, MOBMOD=1
)

VDD=5.0; Vout_lt=3.539; Vp_lt=0.549; Vicm=1.65; Vb=0.93

print("\n=== M3 (PMOS diode, W=10u, L=1u) ===")
# PMOS: VSG=VDD-Vout, VSD=VDD-Vout, VSB=0
VSG3=VDD-Vout_lt; VSD3=VDD-Vout_lt
print(f"VSG={VSG3:.3f}V, VSD={VSD3:.3f}V")
I3,Vth3,_,Vdsat3,_,_,_ = bsim3Ids(PP, 10e-6, 1e-6, VSG3, VSD3, 0)
print(f"  |Vthp|={Vth3:.4f}V, I3={I3*1e6:.2f}uA")

print("\n=== 전체 균형 검토 (LTspice OP 기준) ===")
print(f"  I1={I1*1e6:.2f}uA, I3={I3*1e6:.2f}uA, I5={I5*1e6:.2f}uA")
print(f"  I1-I3={( I1-I3)*1e6:.3f}uA  (→ 0이어야 함, node A KCL)")
print(f"  2*I1-I5={(2*I1-I5)*1e6:.3f}uA  (→ 0이어야 함, tail KCL)")
