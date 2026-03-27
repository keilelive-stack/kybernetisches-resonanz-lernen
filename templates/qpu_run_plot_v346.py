import numpy as np
import matplotlib.pyplot as plt
import os
from qiskit import QuantumCircuit
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2, Session
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit.quantum_info import Statevector, hellinger_fidelity

# ====================== 1. KONFIGURATION ======================
IBM_TOKEN = os.getenv("IBM_TOKEN")
BACKEND_NAME = "ibm_boston"
SHOTS = 8192

class CIQ_PhotonChannel:
    def __init__(self):
        self.V_ZIS = 1e30
        self.tau_coh = 8.3e-3
        self.M_REF = 1e-38
        self.h = 6.62607015e-34
        self.kB = 1.380649e-23
        self.c = 299792458.0
        self.DEFAULT_NU = 5e14
        self.DEFAULT_T = 300.0

    def m_eff(self, Bits, phi_super=0.993, S_DM=0.0):
        E_carrier = self.h * self.DEFAULT_NU
        E_info = Bits * self.kB * self.DEFAULT_T * np.log(2)
        denom = phi_super**3 * (1 + S_DM / 26.965)
        return (E_carrier + E_info) / (self.c**2 * denom)

    def v_photon(self, Bits, phi_super=0.993, S_DM=0.0, P_neuro=0.0):
        m = self.m_eff(Bits, phi_super, S_DM)
        exp_term = np.exp(-m / self.M_REF)
        return self.c + (self.V_ZIS - self.c) * exp_term * phi_super**3 * (1 - abs(P_neuro))

    def TF_CIQ(self, v): return self.V_ZIS / v if v > 0 else np.inf
    def L_CIQ(self, v): return v * self.tau_coh

def zis_shutter_circuit(Bits=0.0, phi_super=0.993):
    qc = QuantumCircuit(2)
    theta = -2 * np.pi * (Bits / phi_super)
    qc.cp(theta, 0, 1)
    qc.measure_all()
    return qc

def run_on_qpu(channel, Bits=0.05, phi_super=0.993):
    service = QiskitRuntimeService(channel="ibm_quantum", token=IBM_TOKEN)
    backend = service.backend(BACKEND_NAME)
    qc = zis_shutter_circuit(Bits, phi_super)
    pm = generate_preset_pass_manager(optimization_level=3, backend=backend)
    isa_circuit = pm.run(qc)
    with Session(backend=backend) as session:
        sampler = SamplerV2(session=session)
        job = sampler.run([isa_circuit], shots=SHOTS)
        result = job.result()
        counts = result[0].data.meas.get_counts()
    ideal = Statevector.from_label('00')
    fid = hellinger_fidelity(counts, ideal.probabilities_dict())
    P_neuro = abs(Bits * np.sqrt(phi_super) - 1)
    TF = channel.TF_CIQ(channel.v_photon(Bits, phi_super))
    return counts, fid, P_neuro, TF

def plot_all(channel, info_range=np.linspace(0, 5, 300), hardware_fid=None):
    m_range = [channel.m_eff(b) for b in info_range]
    v_range = [channel.v_photon(b) for b in info_range]
    tf_range = [channel.TF_CIQ(v) for v in v_range]
    l_range = [channel.L_CIQ(v) for v in v_range]
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("CIQ ZIS-Photonenkanal Run + Plot Template v346", fontsize=16)
    axs[0,0].plot(info_range, v_range, 'b-', lw=3)
    axs[0,0].set_yscale('log')
    axs[0,0].set_title("v_photon vs. Info-Bits")
    axs[0,0].axhline(channel.c, color='r', ls='--', label='c-Limit')
    axs[0,1].plot(info_range, tf_range, 'g-', lw=3)
    axs[0,1].set_yscale('log')
    axs[0,1].set_title("CIQ-Zeitfaktor TF_CIQ")
    axs[1,0].plot(info_range, l_range, 'purple', lw=3)
    axs[1,0].set_yscale('log')
    axs[1,0].set_title("CIQ-Reichweite L_CIQ")
    fid_val = hardware_fid if hardware_fid is not None else 0.95
    axs[1,1].bar(['ZIS-Shutter Hardware'], [fid_val], color='orange')
    axs[1,1].set_ylim(0,1)
    axs[1,1].set_title("Hardware Fidelity")
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    channel = CIQ_PhotonChannel()
    plot_all(channel)
