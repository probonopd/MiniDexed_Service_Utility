class SingleVoiceDumpDecoder:
    """
    Decodes a DX7 single voice dump (VCED format, 155 bytes in 161-byte SysEx).
    Follows the VCED parameter table specification from the DX7II manual.
    """
    def __init__(self, data):
        self.data = data
        self.valid = False
        self.params = {}
        self.decode()

    def decode(self):
        if not self.data or len(self.data) != 161:
            print(f"[SVD DECODER] Data must be exactly 161 bytes, got {len(self.data) if self.data else 'None'}.")
            return
        d = self.data[5:160]  # 155 bytes of VCED voice data
        # Operator parameters (OP1..OP6, 21 params each)
        # Table columns: OP1, OP2, OP3, OP4, OP5, OP6
        self.params['operators'] = []
        for op in range(6):
            base = op * 21
            op_params = {
                # EG Rates
                'R1': d[base+0],   # EG RATE1
                'R2': d[base+1],   # EG RATE2
                'R3': d[base+2],   # EG RATE3
                'R4': d[base+3],   # EG RATE4
                # EG Levels
                'L1': d[base+4],   # EG LEVEL1
                'L2': d[base+5],   # EG LEVEL2
                'L3': d[base+6],   # EG LEVEL3
                'L4': d[base+7],   # EG LEVEL4
                # Keyboard Level Scaling
                'BP': d[base+8],   # BREAK POINT
                'LD': d[base+9],   # LEFT DEPTH
                'RD': d[base+10],  # RIGHT DEPTH
                'LC': d[base+11],  # LEFT CURVE
                'RC': d[base+12],  # RIGHT CURVE
                'RS': d[base+13],  # RATE SCALING
                'AMS': d[base+14], # MODULATION SENSITIVITY
                'TS': d[base+15],  # TOUCH SENSITIVITY
                'TL': d[base+16],  # TOTAL LEVEL
                'PM': d[base+17],  # FREQUENCY MODE (0=ratio, 1=fixed)
                'PC': d[base+18],  # FREQUENCY COARSE
                'PF': d[base+19],  # FREQUENCY FINE
                'PD': d[base+20],  # DETUNE
            }
            self.params['operators'].append(op_params)
        # Pitch EG
        self.params['PR1'] = d[126]  # PEG RATE1
        self.params['PR2'] = d[127]  # PEG RATE2
        self.params['PR3'] = d[128]  # PEG RATE3
        self.params['PR4'] = d[129]  # PEG RATE4
        self.params['PL1'] = d[130]  # PEG LEVEL1
        self.params['PL2'] = d[131]  # PEG LEVEL2
        self.params['PL3'] = d[132]  # PEG LEVEL3
        self.params['PL4'] = d[133]  # PEG LEVEL4
        # Algorithm, feedback, etc.
        self.params['ALS'] = d[134]  # ALGORITHM SELECTOR
        self.params['FBL'] = d[135]  # FEEDBACK LEVEL
        self.params['OPI'] = d[136]  # OSC PHASE INIT
        self.params['LFS'] = d[137]  # LFO SPEED
        self.params['LFD'] = d[138]  # LFO DELAY TIME
        self.params['LPMD'] = d[139] # PITCH MODULATION DEPTH
        self.params['LAMD'] = d[140] # AMP MODULATION DEPTH
        self.params['LFKS'] = d[141] # LFO KEY SYNC
        self.params['LFW'] = d[142]  # LFO WAVE
        self.params['LPMS'] = d[143] # LFO PITCH MOD SENSITIVITY
        self.params['TRNP'] = d[144] # TRANSPOSE
        # Voice name (ASCII, 10 chars)
        name_bytes = d[145:155]
        try:
            self.params['VNAM'] = bytes(name_bytes).decode('ascii', errors='replace').strip()
        except Exception as e:
            print(f"[SVD DECODER] Exception decoding voice name: {e}")
            self.params['VNAM'] = ''
        # Voice name chars (VNAM1..VNAM10)
        for i in range(10):
            self.params[f'VNAM{i+1}'] = d[144+i]
        # Operator enable and select (not always present in all dumps)
        self.params['OPE'] = d[155] if len(d) > 155 else None  # OPERATOR ENABLE
        self.params['OPSEL'] = d[156] if len(d) > 156 else None # OPERATOR SELECT
        self.valid = True

    def get_param(self, key):
        return self.params.get(key)

    def is_valid(self):
        return self.valid
