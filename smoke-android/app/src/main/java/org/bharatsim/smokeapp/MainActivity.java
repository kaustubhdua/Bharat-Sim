package org.bharatsim.smokeapp;
import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Button;

public final class MainActivity extends Activity {
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

        Button action = new Button(this);
        action.setText("Run primary action");
        action.setContentDescription("primary-action");
        action.setOnClickListener(view -> status.setText("Primary action completed"));

        layout.addView(title);
        layout.addView(detail);
        layout.addView(action);
        layout.addView(status);
        setContentView(layout);
    }
}
