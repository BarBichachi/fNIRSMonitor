import numpy as np
import config


class DataProcessor:
    # Handles the scientific calculations and signal quality assessment.
    def __init__(self):
        # Initializes the DataProcessor.
        self.baseline_mean = None
        self._init_mbll_constants()

        # We will check the standard deviation over the last 50 samples (1 second)
        self.quality_buffer_size = 50
        self.raw_buffer = np.zeros((self.quality_buffer_size, len(config.CHANNEL_NAMES) * 2))

        self.alert_history_size = config.ALERT_HISTORY_SECONDS * config.SAMPLE_RATE
        self.alert_history = np.full((len(config.CHANNEL_NAMES), self.alert_history_size), False)

        self.calibration_buffer = []

    def _init_mbll_constants(self):
        # Pre-calculates the matrix needed for the Modified Beer-Lambert Law.
        e_wl1 = config.EXTINCTION_COEFFICIENTS['760nm']
        e_wl2 = config.EXTINCTION_COEFFICIENTS['850nm']
        extinction_matrix = np.array([[e_wl1['O2Hb'], e_wl1['HHb']], [e_wl2['O2Hb'], e_wl2['HHb']]])
        self.inverse_extinction_matrix = np.linalg.inv(extinction_matrix)

    def start_calibration(self):
        # Resets all buffers and states to start a new calibration process.
        print("Data Processor: Starting new calibration.")
        self.calibration_buffer = []
        self.alert_history.fill(False) # Reset alert history on recalibration
        self.baseline_mean = None

    def add_calibration_sample(self, raw_sample):
        # Adds a raw data sample to the calibration buffer.
        self.calibration_buffer.append(raw_sample)

    def finish_calibration(self):
        # Calculates and sets the new baseline from the calibration buffer.
        if len(self.calibration_buffer) < config.SAMPLE_RATE * (config.CALIBRATION_DURATION - 2):
            print("Data Processor: Calibration failed, not enough data.")
            self.calibration_buffer = []
            return False, None  # Return success status and baseline data

        self.baseline_mean = np.mean(self.calibration_buffer, axis=0)
        self.calibration_buffer = []
        print("Data Processor: New baseline established.")
        return True, self.baseline_mean  # Return success status and baseline data

    def abort_calibration(self):
        # Clears the calibration buffer.
        print("Data Processor: Calibration aborted.")
        self.calibration_buffer = []

    def check_for_alert(self, o2hb_values, threshold, duration_s):
        # Checks if the current data triggers a 'Cognitive Load' alert.
        is_above_threshold = o2hb_values > threshold

        # --- Update Alert History Buffer ---
        # Shift history to the left and add the new boolean values at the end
        self.alert_history = np.roll(self.alert_history, -1, axis=1)
        self.alert_history[:, -1] = is_above_threshold

        # --- Check if the rule is met ---
        samples_needed = duration_s * config.SAMPLE_RATE
        # Check the most recent `samples_needed` for each channel
        recent_history = self.alert_history[:, -samples_needed:]

        # The alert triggers if ALL recent samples for ANY channel are True
        if np.any(np.all(recent_history, axis=1)):
            return "Cognitive Load"

        return "Nominal"

    def _calculate_signal_quality(self):
        # Calculates the signal quality for each of the 8 physical channels.
        quality_states = []
        # We check the standard deviation of the raw light intensity for each channel's first wavelength
        for i in range(len(config.CHANNEL_NAMES)):
            channel_index = i * 2
            std_dev = np.std(self.raw_buffer[:, channel_index])

            # Determine state based on standard deviation thresholds
            if std_dev < 2:  # Very low fluctuation = flat signal
                quality_states.append('red')
            else:  # Healthy fluctuation
                quality_states.append('green')
        return quality_states

    def process_sample_with_baseline(self, raw_sample, alert_rules):
        # Converts a raw sample to processed data and checks for alerts.
        self.raw_buffer[:-1] = self.raw_buffer[1:]
        self.raw_buffer[-1] = raw_sample

        if self.baseline_mean is None:
            return None

        delta_od = -np.log(np.array(raw_sample) / self.baseline_mean)
        processed_data = self.calculate_hemoglobin(delta_od)
        processed_data['quality'] = self._calculate_signal_quality()

        # --- Check for alerts using the new data and provided rules ---
        alert_state = self.check_for_alert(
            np.array(processed_data['O2Hb']),
            alert_rules['threshold'],
            alert_rules['duration']
        )
        processed_data['alert_state'] = alert_state

        return processed_data

    def calculate_hemoglobin(self, delta_od):
        # Calculates O2Hb and HHb changes from the optical density change.
        num_channels = len(delta_od) // 2
        delta_od_reshaped = delta_od.reshape(num_channels, 2)
        delta_c = self.inverse_extinction_matrix @ delta_od_reshaped.T / (config.DPF * config.INTEROPTODE_DISTANCE)
        processed_data = {'O2Hb': delta_c[0, :].tolist(), 'HHb': delta_c[1, :].tolist()}
        return processed_data