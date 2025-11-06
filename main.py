{% if assignment.is_flight %}
    <div class="flight-number">
        {{ assignment.airline }}{{ assignment.flight_number }}
    </div>
    <div class="route">
        {{ assignment.origin }}-{{ assignment.destination }}
        {% if assignment.departure_stand %} | {{ assignment.departure_stand }}{% endif %}
    </div>
    <div class="flight-times">
        {{ assignment.departure_time }} - {{ assignment.arrival_time }}
        {% if assignment.time_advanced %}<span class="status-on-time">On Time</span>{% endif %}
        {% if assignment.time_delayed %}<span class="status-delayed">Delayed</span>{% endif %}
        {% if assignment.aircraft_registration %} | {{ assignment.aircraft_registration }}{% endif %}
    </div>
{% else %}
    <div style="font-weight: bold; color: #495057;">
        {{ assignment.activity_code }}
    </div>
    <div style="font-size: 0.7em; color: #666;">
        {{ assignment.start_time }} - {{ assignment.end_time }}
    </div>
{% endif %}