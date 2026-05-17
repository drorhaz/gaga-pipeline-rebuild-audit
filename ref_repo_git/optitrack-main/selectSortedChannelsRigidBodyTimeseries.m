function [channelRigidBodyTsorted] = selectSortedChannelsRigidBodyTimeseries(cfg)
% This function sorts the output of getChannelLevelRigidBodyTimeseries()
% based on the order of channels in the SPM object, using the mapping
% provided in the slot2sens.csv file. It discards any channel-level rigid
% body timeseries for which no matching sensors are found in the SPM
% object.
%
% INPUT:
%   - D: the SPM D object.
%   - slot2sens: the CSV or Excel file containing the mapping from
%   scannercast slots to OPM sensors.
%   - sensorPositions: the scannercast positions file, generated from STL
%   files using extractSensorPositions_V3().
%   - channelLevelRbTimeseries: the rigid body movement timeseries,
%   extracted from Motive using getChannelLevelRigidBodyTimeseries().
%
% OUTPUT:
%   - channelLevelRbTimeseriesChestSorted: the channel level rigid body 
%   timeseriese, sorted in the same order as the channels as the SPM D
%   object.
%
% % Example use:
% cfg						    = [];
% cfg.D                         = D;
% cfg.slot2sens                 = 'slot2sens.csv';
% cfg.sensorPositions           = chestSensorPositions;
% cfg.channelLevelRbTimeseries  = channelLevelRbTimeseries;
% channelRigidBodyTsorted = selectSortedChannelsRigidBodyTimeseries(cfg);
%
% Author:	Sascha Woelk (s.wolk.16@ucl.ac.uk)
% MIT License

% Get the channels from the SPM object
chansD = cfg.D.chanlabels(cfg.D.indchantype('meg'));

% Read slot2sens
slot2sens = readtable(cfg.slot2sens);

% Check if slot2sens.csv has the right column names (slot and channel and sensor name)
if ~sum(ismember(slot2sens.Properties.VariableNames,'slot'))
    error('slot2sens.csv needs a column labelled ''slot''');
end

if ~sum(ismember(slot2sens.Properties.VariableNames,'sensor'))
    error('slot2sens.csv needs a column labelled ''sensor''');
end

% Find the index of slot2sens.slot entries in the scannercast slots
[~, sortIdx] = ismember(slot2sens.slot, cfg.sensorPositions.slot);

% Filter out unmatched entries if needed
validIdx = sortIdx > 0;
slot2sens_sorted = slot2sens(validIdx, :);          
sortIdx_filtered = sortIdx(validIdx);   

% Sort slot2sens according to order in headcast slots
[~, order] = sort(sortIdx_filtered);
slot2sens_sorted = slot2sens_sorted(order, :);

% Map the format of the sensors to the format of the lvm files
[numeric_slot2sens_sensors, ~, ~] = map_slot2sens_to_lvm(chansD, slot2sens_sorted.sensor);

% Initialize an empty cell array for the complete list of channels
allChannelsSelected = {};

% Go through each sensor
chanIdx = 0;
channelRigidBodyT = cell(length(chansD),1);
for sensIdx = 1:numel(numeric_slot2sens_sensors)
    
    % Get the current sensor number
    currentSens = num2str(numeric_slot2sens_sensors(sensIdx));

	% Find the labels in rawData that match the slot2sens
    pattern = ['[XYZ](' currentSens ')'];
	idx = find(~cellfun(@isempty, regexp(chansD, pattern)));
	channels = chansD(idx);

    % Append the channels to the complete list of channels
    allChannelsSelected = [allChannelsSelected(:); channels(:)];
    
    % Append rigid body data for all relevant channels (i.e. one per
    % orientation)
	for sensChanIdx = 1:length(channels)
		chanIdx = chanIdx + 1;
		if ismember(channels{sensChanIdx}(1),{'X','Y','Z'})
			channelRigidBodyT{chanIdx} = cfg.channelLevelRbTimeseries{slot2sens{sensIdx,1},2};
		else
			error("Cannot identify channel orientation")
		end
	end
end

% Assure the sorting of channel RigidBody Timeseries is correct
[~, sortIdx] = ismember(chansD, allChannelsSelected);
% Ensure there are no missing matches
if any(sortIdx == 0)
    error('Some channels in the SPM object are not found in the slot2sens file.');
end

% Sort channelLevelRbTimeseriesHead using the index
channelRigidBodyTsorted = channelRigidBodyT(sortIdx);

end

%% The below functions originate from info2pos_neuro1.m (Author: 06/2025 Nicholas Alexander (n.alexander@ucl.ac.uk))

function [numeric_slot2sens_sensors, numeric_lvm_sensors, lvm_axis_letters] = map_slot2sens_to_lvm(lvm_channels, slot2sens_sensors)
% Checks if the channels match one of the expected formats for lvm channel 
% names and whether the slot2sens sensors column can be matched to those
% channels. Returns this info in a common numeric format, as well as the
% channel axes labels. 
%
% The idea is that if the format changes this function can be updates to
% include new format checks, but always converting back to a numeric format
% that can match something user friendly. 

% It might be better to work these out from the lvm, but it works for now
module_letters = 'ABCDEFGH';
axes_letters = 'XYZ';


% Checks
if numel(unique(slot2sens_sensors)) < numel(slot2sens_sensors)
    error('Duplicate entries found in slot2sens_sensors. Each sensor must be unique.');
end
if isnumeric(slot2sens_sensors)
    slot2sens_sensors = cellstr(string(slot2sens_sensors));
end
if isnumeric(lvm_channels)
    lvm_channels = cellstr(string(lvm_channels));
end

lvm_axis_letters = regexp(lvm_channels, ['(^[',axes_letters,'])|([',axes_letters,']$)'], 'match');
% axis_mod = (cellfun(@(x) ~isempty(x) * (find(axes_letters == x{1}(end))), axis_letters) - 1) * length(lvm_channels) / length(axes_letters);
lvm_channels_no_axis = regexprep(lvm_channels, ['(^[',axes_letters,'])|(_[',axes_letters,']$)'], '');

% These format names are a shorthand for the three posible options outlined
% in the main function description. 
is_B1 = all(cellfun(@is_B1, lvm_channels_no_axis));
is_num = all(cellfun(@is_num, lvm_channels_no_axis));
is_B9 = all(cellfun(@is_B9, lvm_channels_no_axis));
if is_B1
    lvm_channels_format = 'B1';
    row = cellfun(@(s) str2double(s(2)), lvm_channels_no_axis);
    col = cellfun(@(s) find(module_letters == s(1)), lvm_channels_no_axis);
    numeric_lvm_sensors = ((col - 1) * 8 + row);
elseif is_num
    lvm_channels_format = 'num';
    numeric_lvm_sensors = str2double(lvm_channels_no_axis);
elseif is_B9
    lvm_channels_format = 'B9';
    col = cellfun(@(s) find(module_letters == s(1)), lvm_channels_no_axis);
    row = cellfun(@(s) str2double(s(2:end)), lvm_channels_no_axis);
    numeric_lvm_sensors = ((col - 1) * 8 + row);
else
    error('Could not recognise the format of lvm channels.');
end

is_B1 = all(cellfun(@is_B1, slot2sens_sensors));
is_num = all(cellfun(@is_num, slot2sens_sensors));
is_B9 = all(cellfun(@is_B9, slot2sens_sensors));
if is_B1
    row = cellfun(@(s) str2double(s(2)), slot2sens_sensors);
    col = cellfun(@(s) find(module_letters == s(1)), slot2sens_sensors);
    numeric_slot2sens_sensors = (col - 1) * 8 + row;
elseif is_num
    numeric_slot2sens_sensors = str2double(slot2sens_sensors);
elseif is_B9
    col = cellfun(@(s) find(module_letters == s(1)), slot2sens_sensors);
    row = cellfun(@(s) str2double(s(2:end)), slot2sens_sensors);
    numeric_slot2sens_sensors = (col - 1) * 8 + row;
else
    error('Could not recognise the format of slot2sens.');
end

switch lvm_channels_format
    case 'B1'
        row = mod(numeric_slot2sens_sensors - 1, 8) + 1;
        col = floor((numeric_slot2sens_sensors - 1) / 8) + 1;
        slot2sens_sensors_mapped = arrayfun(@(c, r) sprintf('%c%d', module_letters(c), r), col, row, 'UniformOutput', false);
    case 'num'
        slot2sens_sensors_mapped = cellstr(string(numeric_slot2sens_sensors));
    case 'B9'
        row = mod(numeric_slot2sens_sensors - 1, 8) + 1;
        col = floor((numeric_slot2sens_sensors - 1) / 8) + 1;
        slot2sens_sensors_mapped = arrayfun(@(c, r) sprintf('%c%d', module_letters(c), ((c-1)*8 + r)), col, row, 'UniformOutput', false);
    
end

% Check what sensors match between slot2sens and lvm data. 
match_flags = ismember(slot2sens_sensors_mapped, lvm_channels_no_axis);
n_match = sum(match_flags);
n_total = numel(slot2sens_sensors_mapped);

fprintf('%d of %d sensors in slot2sens matched .lvm channels.\n', n_match, n_total);

% Report unmatched in slot2sens
if any(~match_flags)
    unmatched = slot2sens_sensors_mapped(~match_flags);
    fprintf('Sensors in slot2sens not found in D object (check whether these were marked as bad channels):\n');
    disp(unmatched(:)');
end

% Report unmatched in lvm
reverse_flags = ismember(lvm_channels_no_axis, slot2sens_sensors_mapped);
if any(~reverse_flags)
    unmatched_lvm = lvm_channels(~reverse_flags);
    fprintf('Channels in D object not referenced in slot2sens:\n');
    disp(unmatched_lvm(:)');
end

end

function valid = is_B9(str)
% At one point the lvm files were A1-8, B9-16 etc. 
module_letters = 'ABCDEFGH';
if isempty(str) || length(str) < 2
    valid = false;
    return;
end
colChar = str(1);
numPart = str2double(str(2:end));

if ~ismember(colChar, module_letters) || isnan(numPart)
    valid = false;
    return;
end

colIdx = find(module_letters == colChar);
minValid = (colIdx - 1) * 8 + 1;
maxValid = colIdx * 8;

valid = numPart >= minValid && numPart <= maxValid;
end

function valid = is_B1(str)
% They can also be A1-8, B1-8 etc. Users may also use this for slot2sens
valid = false;
if isempty(str) || length(str) < 2
    return;
end
col = str(1);
row = str2double(str(2:end));
if ismember(col, 'A':'H') && ~isnan(row) && row >= 1 && row <= 8
    valid = true;
end
end

function valid = is_num(str)
% For data that is X1-64. Could be used for slot2sens
val = str2double(str);
valid = ~isnan(val) && val >= 1 && val <= 64;
end