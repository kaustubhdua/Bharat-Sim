package org.bharatsim.smokeapp;

import android.app.Activity;
import android.os.Bundle;
import android.os.SystemClock;
import android.graphics.Color;
import android.util.Log;
import android.view.Gravity;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Button;

import java.net.HttpURLConnection;
import java.net.URL;

public final class MainActivity extends Activity {
    private static final String TAG = "BharatSimNetworkProbe";
    private static final String PROBE_URL = BuildConfig.PROBE_URL;
    private static final int PROBE_BYTES = 2_000_000;
    private int probeSequence = 0;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setGravity(Gravity.CENTER);
        layout.setPadding(32, 32, 32, 32);
        layout.setBackgroundColor(Color.rgb(245, 248, 242));

        TextView title = new TextView(this);
        title.setText("BharatSim Android smoke test");
        title.setContentDescription("fixture-title");
        title.setTextSize(24);
        title.setTextColor(Color.rgb(30, 70, 45));
        title.setGravity(Gravity.CENTER);

        TextView detail = new TextView(this);
        detail.setText("REAL EMULATOR FIXTURE\nInstall • Launch • Observe • Collect logs");
        detail.setTextSize(16);
        detail.setTextColor(Color.DKGRAY);
        detail.setGravity(Gravity.CENTER);
        detail.setPadding(0, 24, 0, 0);

        TextView status = new TextView(this);
        status.setText("Ready");
        status.setTextSize(16);
        status.setTextColor(Color.rgb(30, 70, 45));
        status.setGravity(Gravity.CENTER);
        status.setContentDescription("journey-status");

        TextView networkStatus = new TextView(this);
        networkStatus.setText("Network probe not run");
        networkStatus.setTextSize(14);
        networkStatus.setTextColor(Color.rgb(30, 70, 45));
        networkStatus.setGravity(Gravity.CENTER);
        networkStatus.setContentDescription("network-probe-status");

        Button action = new Button(this);
        action.setText("Run primary action");
        action.setContentDescription("primary-action");
        action.setOnClickListener(view -> {
            status.setText("Primary action completed");
            final int sequence = ++probeSequence;
            networkStatus.setText("Network probe running");
            new Thread(() -> performNetworkProbe(networkStatus, sequence)).start();
        });

        layout.addView(title);
        layout.addView(detail);
        layout.addView(action);
        layout.addView(status);
        layout.addView(networkStatus);
        setContentView(layout);
    }

    private void performNetworkProbe(TextView target, int sequence) {
        String transport = activeTransport();
        for (int attempt = 1; attempt <= 4; attempt++) {
            long started = SystemClock.elapsedRealtime();
            int statusCode = -1;
            int bytesRead = 0;
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(PROBE_URL).openConnection();
                connection.setConnectTimeout(5000);
                connection.setReadTimeout(30000);
                connection.setRequestMethod("GET");
                connection.setRequestProperty("Connection", "close");
                connection.setRequestProperty("Accept-Encoding", "identity");
                connection.setRequestProperty("Cache-Control", "no-cache");
                connection.setRequestProperty("Range", "bytes=0-" + (PROBE_BYTES - 1));
                connection.setUseCaches(false);
                statusCode = connection.getResponseCode();
                if (statusCode != 200 && statusCode != 206) {
                    throw new java.io.IOException("Unexpected HTTP status " + statusCode);
                }
                // Read exactly the requested bounded payload. Do not wait for
                // server EOF after the byte count is satisfied: a CDN or proxy
                // may keep the connection alive after delivering the requested bytes.
                try (java.io.InputStream input = connection.getInputStream()) {
                    byte[] buffer = new byte[8192];
                    while (bytesRead < PROBE_BYTES) {
                        int wanted = Math.min(buffer.length, PROBE_BYTES - bytesRead);
                        int count = input.read(buffer, 0, wanted);
                        if (count == -1) break;
                        bytesRead += count;
                    }
                }
                if (bytesRead != PROBE_BYTES) {
                    throw new IllegalStateException("Expected " + PROBE_BYTES + " probe bytes, received " + bytesRead);
                }
                long duration = SystemClock.elapsedRealtime() - started;
                Log.i(TAG, "BHARATSIM_NETWORK_PROBE status=HTTP_" + statusCode + " duration_ms=" + duration
                        + " transport=" + transport + " probe=" + sequence
                        + " bytes_read=" + bytesRead + " attempts=" + attempt);
                final String message = "HTTP " + statusCode + " · " + duration + " ms · " + transport
                        + " · probe " + sequence + " · bytes " + bytesRead + " · attempts " + attempt;
                runOnUiThread(() -> target.setText(message));
                return;
            } catch (Exception exception) {
                // Transient host/emulator connection resets can occur in hosted CI. Retry
                // bounded I/O failures with backoff; keep attempt counts in logcat
                // and UI evidence. Malformed payloads are not retried, and a final
                // failure is never reported as a successful measurement.
                if (exception instanceof java.io.IOException && attempt < 4) {
                    Log.w(TAG, "BHARATSIM_NETWORK_PROBE retrying sequence=" + sequence
                            + " attempt=" + attempt + " after=" + exception.getClass().getSimpleName(), exception);
                    try {
                        Thread.sleep(attempt * 1000L);
                    } catch (InterruptedException interrupted) {
                        Thread.currentThread().interrupt();
                        Log.e(TAG, "BHARATSIM_NETWORK_PROBE interrupted sequence=" + sequence, interrupted);
                        runOnUiThread(() -> target.setText("Network probe failed: InterruptedException"));
                        return;
                    }
                    continue;
                }
                Log.e(TAG, "BHARATSIM_NETWORK_PROBE status=ERROR transport=" + transport
                        + " probe=" + sequence + " attempts=" + attempt, exception);
                final String message = "Network probe failed: " + exception.getClass().getSimpleName();
                runOnUiThread(() -> target.setText(message));
                return;
            } finally {
                if (connection != null) {
                    connection.disconnect();
                }
            }
        }
    }

    private String activeTransport() {
        ConnectivityManager manager = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
        Network active = manager == null ? null : manager.getActiveNetwork();
        NetworkCapabilities caps = manager == null || active == null ? null : manager.getNetworkCapabilities(active);
        if (caps == null) return "UNKNOWN";
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) return "CELLULAR";
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) return "ETHERNET";
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) return "WIFI";
        return "OTHER";
    }
}
