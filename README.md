# WORKOUT TRACKER
#### Video Demo:  https://youtu.be/xnlz7QKqde4
#### Description:
##### Overview
So this is a python flask based web application which serves as a workout tracker/logger where users can register accounts and keep a handy and clean log of their workouts.
This app allows for seamless exercise logging (i.e., record number of sets, repitions and weight) for a particular exercise in a workout.

Dashboard
This is the main home page of the web application. It contains a welcome message that welcomes the user (session[user]).
Page displays total workouts, total weight lifted and last workout as of the workout table in the database referenced by the user_id.(foreign key).

Displays a button "Start a Workout" which redirects to: /log_workout.

Also Displays lists of top five recent workouts logged for the specific user.

Progress Visualizing
(template: analytics.html)
Other that being a workout logger it serves as a tool to visualize your progress over time based on the data logged in so users can see their trend of how much they're lifting
which is a seriously underrated tool to keep seeing results in the gym when it comes to muscle building.
Charts:
1. Progression chart with selection filter for exercise type: Allows user to see a line chart of weights used at a selected period of date.
2.sets per workout: shows how much volume (sets * reps) the user did at given dates as a bar chart.
In addition to charts it also shows cards up top mentioning data on: 1. Total Workouts and 2. Total Weight Lifted (Lifetime Workout Stats)

History Tab
(template: history.html)
The app also provides users with a history tab that lists all of the workouts they've logged in neatly styles as cards using css.
It also displays a fully-fleged calendar which highlights days with colour filled circle where the user worked out.

Workout Logger
(template: log_workout.html)
Application provides a user friendly and very appealing simple workout logger which lists all the exercises available in the database (table:exercise) and also implements a very well designed search bar.
The exercises can be selected and logged in (viewed on the right side of the screen) and each set can be logged in sequentially. Essentially having a set of multiple exercises wrapped up in a card with multiple sets with it's corresponding repitions and weight used.

website also provides a log out button which clears user session[].

I have styled the website quite heavily (relative to my experience with web development) using bootstrap framework along with some specific CDNs for calendar generation (history.html) and icons.
I have also themed the web app with orange and grey as the main colours with subtle teal accents.
