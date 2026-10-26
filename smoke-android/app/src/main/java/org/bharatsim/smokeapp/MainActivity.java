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

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class MainActivity extends Activity {
    private static final String TAG = "BharatSimNetworkProbe";
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
        long started = SystemClock.elapsedRealtime();
        String transport = activeTransport();
        int statusCode = -1;
        // Resolve the public endpoint on the host runner and pin its IPv4 here,
        // so guest DNS is not needed. The explicit Host header preserves the
        // intended virtual host while traffic traverses the emulator's cellular path.
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress(InetAddress.getByName(BuildConfig.PROBE_IP), 80), 10000);
            socket.setSoTimeout(10000);
            OutputStream output = socket.getOutputStream();
            String request = "GET / HTTP/1.1\r\n"
                    + "Host: example.com\r\n"
                    + "User-Agent: BharatSimNetworkProbe/1.0\r\n"
                    + "Connection: close\r\n\r\n";
            output.write(request.getBytes(StandardCharsets.US_ASCII));
            output.flush();

            BufferedReader reader = new BufferedReader(
                    new InputStreamReader(socket.getInputStream(), StandardCharsets.ISO_8859_1));
            String statusLine = reader.readLine();
            Matcher matcher = statusLine == null ? null
                    : Pattern.compile("^HTTP/1\\.[01] (\\d{3})(?: .*)?$").matcher(statusLine);
            if (matcher == null || !matcher.matches()) {
                throw new IllegalStateException("Invalid HTTP status line from pinned public endpoint");
            }
            statusCode = Integer.parseInt(matcher.group(1));
            // Read the response through EOF so duration includes the actual round trip.
            while (reader.readLine() != null) { }
        } catch (Exception exception) {
            Log.e(TAG, "BHARATSIM_NETWORK_PROBE status=ERROR transport=" + transport + " probe=" + sequence, exception);
            final String message = "Network probe failed: " + exception.getClass().getSimpleName();
            runOnUiThread(() -> target.setText(message));
            return;
        }
        long duration = SystemClock.elapsedRealtime() - started;
        if (statusCode >= 200 && statusCode < 400) {
            Log.i(TAG, "BHARATSIM_NETWORK_PROBE status=HTTP_" + statusCode + " duration_ms=" + duration + " transport=" + transport + " probe=" + sequence);
            final String message = "HTTP " + statusCode + " · " + duration + " ms · " + transport + " · probe " + sequence;
            runOnUiThread(() -> target.setText(message));
        } else {
            Log.e(TAG, "BHARATSIM_NETWORK_PROBE status=HTTP_" + statusCode + " duration_ms=" + duration + " transport=" + transport + " probe=" + sequence);
            final String message = "Network probe returned HTTP " + statusCode;
            runOnUiThread(() -> target.setText(message));
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
