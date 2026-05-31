%% clear workspace
clear; clc; close all;

%% data input
raw_data = {
    '1778268136.6457126,减速,0.75,17.93,0.0,-2.106622,0.915111,2.108187,0.823424,0.098867,1.739534'
    '1778268136.677259,减速,0.75,17.93,0.0,-2.34588,1.025169,2.282845,0.822891,0.098335,1.74992'
    '1778268136.677259,减速,0.75,17.93,0.0,-2.822003,1.240501,2.665658,0.823424,0.097536,1.753648'
    '1778268136.7088192,急刹车,0.95,17.93,0.0,-3.381866,0.099242,1.950277,0.825022,0.095938,1.76004'
    '1778268136.7088192,急刹车,0.95,17.93,0.0,-4.724103,1.754906,4.161019,0.825554,0.095405,1.763502'
    '1778268136.7391276,急刹车,0.95,17.93,0.0,-5.829474,2.293236,5.022347,0.824755,0.095938,1.764035'
    '1778268136.7391276,急刹车,0.95,17.93,0.0,-8.030646,3.329222,6.687581,0.82369,0.096471,1.765632'
    '1778268136.771028,急刹车,0.95,17.93,0.0,-10.270099,4.379564,8.362386,0.823424,0.096471,1.765899'
    '1778268136.771028,急刹车,0.95,17.93,0.0,-12.581329,5.501683,10.183138,0.823424,0.095938,1.764567'
    '1778268136.8029947,急刹车,0.95,17.93,0.0,-13.890069,6.097435,11.089925,0.823956,0.096204,1.764301'
    '1778268136.8029947,急刹车,0.95,17.93,0.0,-14.574347,6.358226,11.604329,0.825022,0.095672,1.764301'
    '1778268136.8343532,急刹车,0.95,17.93,0.0,-15.715606,6.843919,12.487191,0.823956,0.095405,1.764834'
    '1778268136.8343532,急刹车,0.95,17.93,0.0,-12.741632,5.379661,10.044369,0.823956,0.095938,1.764567'
    '1778268136.8642125,减速,0.75,17.93,0.0,-0.673468,-0.10652,0.655892,0.824755,0.095938,1.764301'
    '1778268136.8642125,加速,0.75,17.93,0.0,0.589813,-0.70945,-0.222184,0.825554,0.095139,1.763768'
    '1778268136.895242,加速,0.75,17.93,0.0,0.577851,-0.690309,-0.222184,0.82662,0.095938,1.762703'
    '1778268136.895242,加速,0.75,17.93,0.0,0.546747,-0.683132,-0.226969,0.825821,0.096737,1.763236'
    '1778268136.9267766,加速,0.75,17.93,0.0,0.556317,-0.675954,-0.238932,0.825821,0.09727,1.764035'
    '1778268136.9267766,加速,0.75,17.93,0.0,0.525214,-0.649635,-0.250895,0.825554,0.095938,1.762969'
    '1778268136.9590771,加速,0.75,17.93,0.0,0.498895,-0.649635,-0.231755,0.825821,0.094606,1.761904'
    '1778268136.9590771,加速,0.75,17.93,0.0,0.49411,-0.613747,-0.241325,0.825554,0.095139,1.761638'
    '1778268136.9905822,加速,0.75,17.93,0.0,0.472577,-0.611354,-0.241325,0.825288,0.095938,1.761638'
    '1778268136.9906323,normal,0.9,17.93,0.0,0.116083,-0.161549,-0.083415,0.824223,0.095938,1.760839'
    '1778268137.0219474,normal,0.9,17.93,0.0,-0.022687,0.020286,-0.006852,0.825022,0.097536,1.760572'
    '1778268137.0219474,normal,0.9,17.93,0.0,-0.013116,0.010716,0.007503,0.825288,0.096737,1.76217'
    '1778268137.0529475,normal,0.9,17.93,0.0,-0.008331,-0.006032,-0.025993,0.824755,0.095139,1.762969'
};

%% parse data
n = length(raw_data);
timestamp = zeros(n, 1);
event_label = cell(n, 1);
speed = zeros(n, 1);
acc_x = zeros(n, 1);
acc_y = zeros(n, 1);
acc_z = zeros(n, 1);

for i = 1:n
    parts = strsplit(raw_data{i}, ',');
    timestamp(i) = str2double(parts{1});
    event_label{i} = parts{2};
    speed(i) = str2double(parts{4});
    acc_x(i) = str2double(parts{6});
    acc_y(i) = str2double(parts{7});
    acc_z(i) = str2double(parts{8});
end

t0 = timestamp(1);
rel_time = timestamp - t0;

%% event color mapping
unique_events = {'急刹车','减速','加速','normal'};
event_colors = [1.0 0.2 0.2; 1.0 0.6 0.0; 0.2 0.7 0.2; 0.3 0.5 1.0];

%% Figure 1 三轴加速度
figure(1); set(gcf,'Position',[100,100,1200,500]);
plot(rel_time,acc_x,'-','LineWidth',2,'Color',[0.8 0.2 0.2]); hold on;
plot(rel_time,acc_y,'-','LineWidth',2,'Color',[0.2 0.6 0.2]);
plot(rel_time,acc_z,'-','LineWidth',2,'Color',[0.2 0.2 0.8]);

y_bottom = min([acc_x;acc_y;acc_z]) - 2;
for i=1:n
    idx = find(strcmp(unique_events,event_label{i}));
    if ~isempty(idx)
        scatter(rel_time(i),y_bottom,80,event_colors(idx,:),'filled','MarkerEdgeColor','k');
    end
end

xlabel('Relative Time (s)','FontSize',12);
ylabel('Acceleration (m/s^2)','FontSize',12);
title('Three-Axis Acceleration vs Time','FontSize',14,'FontWeight','bold');

h1 = plot(nan,nan,'-','LineWidth',2,'Color',[0.8 0.2 0.2]);
h2 = plot(nan,nan,'-','LineWidth',2,'Color',[0.2 0.6 0.2]);
h3 = plot(nan,nan,'-','LineWidth',2,'Color',[0.2 0.2 0.8]);
he1 = scatter(nan,nan,80,event_colors(1,:),'filled','MarkerEdgeColor','k');
he2 = scatter(nan,nan,80,event_colors(2,:),'filled','MarkerEdgeColor','k');
he3 = scatter(nan,nan,80,event_colors(3,:),'filled','MarkerEdgeColor','k');
he4 = scatter(nan,nan,80,event_colors(4,:),'filled','MarkerEdgeColor','k');
legend([h1,h2,h3,he1,he2,he3,he4],...
    {'Longitudinal X','Lateral Y','Vertical Z','急刹车','减速','加速','normal'},'Location','best');

yl = ylim;
patch([0.034 0.193 0.193 0.034],[yl(1) yl(1) yl(2) yl(2)],'red','FaceAlpha',0.08,'EdgeColor','none');
patch([0.224 0.350 0.350 0.224],[yl(1) yl(1) yl(2) yl(2)],'green','FaceAlpha',0.08,'EdgeColor','none');
grid on; hold off;

%% Figure 2 车速
figure(2); set(gcf,'Position',[100,650,1200,350]);
plot(rel_time,speed,'b-','LineWidth',2.5); hold on;
scatter(rel_time,speed,40,'b','filled');
for i=1:n
    idx = find(strcmp(unique_events,event_label{i}));
    if ~isempty(idx)
        scatter(rel_time(i),speed(i),100,event_colors(idx,:),'filled','MarkerEdgeColor','k');
    end
end
xlabel('Relative Time (s)','FontSize',12);
ylabel('Speed (m/s)','FontSize',12);
title('Speed Trend','FontSize',14,'FontWeight','bold');
ylim([speed(1)-0.05, speed(1)+0.05]);

he = gobjects(4,1);
for k=1:4
    he(k) = scatter(nan,nan,80,event_colors(k,:),'filled','MarkerEdgeColor','k');
end
legend(he,unique_events,'Location','best'); grid on;
text(mean(rel_time),speed(1)+0.03,'NOTE: Speed is constant (17.93 m/s)','FontSize',11,'Color','red','FontWeight','bold','HorizontalAlignment','center');
hold off;

%% Figure 3 纵向加速度
figure(3); set(gcf,'Position',[100,200,1200,400]);
plot(rel_time,acc_x,'r-','LineWidth',2.5); hold on;
scatter(rel_time,acc_x,60,'r','filled');

xlabel('Relative Time (s)','FontSize',12);
ylabel('Longitudinal Acceleration X (m/s^2)','FontSize',12);
title('Longitudinal Acceleration and Driving Events','FontSize',14,'FontWeight','bold');

yl = ylim;
patch([0.034 0.193 0.193 0.034],[yl(1) yl(1) yl(2) yl(2)],'red','FaceAlpha',0.1,'EdgeColor','none');
patch([0.224 0.350 0.350 0.224],[yl(1) yl(1) yl(2) yl(2)],'green','FaceAlpha',0.1,'EdgeColor','none');

[min_acc,min_idx] = min(acc_x);
plot(rel_time(min_idx),min_acc,'ko','MarkerSize',12,'LineWidth',2);
text(rel_time(min_idx)+0.01,min_acc,sprintf(' Peak: %.2f',min_acc),'FontSize',12,'FontWeight','bold');
grid on; hold off;

%% 输出结果
fprintf('All figures generated successfully!\n');
fprintf('Peak deceleration: %.2f at t = %.3f s\n', min_acc, rel_time(min_idx));
