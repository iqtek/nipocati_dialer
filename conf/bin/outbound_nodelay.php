#!/usr/bin/php
<?php

function get_context($exts, $context) {
	$start = false;
	$ret = array();
	for ($i=0;$i<count($exts);$i++) {
		if (preg_match("/^\[{$context}\]/", $exts[$i])) {
			$start = true;
			break;
		}
	}
	if (!$start) {
		return false;
	}
	$i++;
	for (;$i<count($exts);$i++) {
		if (preg_match("/^\[\S+\]/", $exts[$i])) {
			return $ret;
		}
		$ret[] = $exts[$i];
	}
	if (strlen($ret)) {
		return $ret;
	}
	return false;
}

function contexts_plain($contexts) {
	$text = "";
	foreach($contexts as $c => $lines) {
		$text .= "[$c]\n";
		for ($i=0;$i<count($lines);$i++) {
			$text .= trim($lines[$i])."\n";
		}
		$text .= "\n\n";
	}
	
	return $text;
}

function array_insert(&$array, $position, $insert)
{
    if (is_int($position)) {
        array_splice($array, $position, 0, $insert);
    } else {
        $pos   = array_search($position, array_keys($array));
        $array = array_merge(
            array_slice($array, 0, $pos),
            $insert,
            array_slice($array, $pos)
        );
    }
}


$file = file('/etc/asterisk/extensions_additional.conf');
$context = get_context($file, 'outbound-allroutes');
foreach ($context as $line) {
	if (preg_match("/include => (outrt-\d+)/", $line, $m)) {
		$line = str_replace($m[1], "{$m[1]}-dialer", $line);
		$route_context = preg_replace("/(Macro\(dialout-trunk)(,\d+)/", "$1-dialer$2", get_context($file, $m[1]));
		$route_context = preg_replace("/(Macro\(outisbusy.*)/", "Hangup()", $route_context);
		$contexts["{$m[1]}-dialer"] = $route_context;
		// exten => 93012496,n,Macro(dialout-trunk,3,${EXTEN:1},,off)
	}
	$contexts['outbound-allroutes-dialer'][] = $line;
}

$macro_context = preg_replace("/(s-\w+,n,)Playback\(\S+\)/", "$1NoOp()", get_context($file, 'macro-dialout-trunk'));
$macro_context = preg_replace("/(s-\w+,n,)Playtones\(\S+\)/", "$1NoOp()", $macro_context);
$macro_context = preg_replace("/(s-\w+,n,Busy)\(\d+\)/", "$1()", $macro_context);
$macro_context = preg_replace("/(s-\w+,n,Congestion)\(\d+\)/", "$1()", $macro_context);

foreach ($macro_context as $i => $ext) {
//	echo "...";
	if (preg_match("/(s,n,)Dial\(/", $ext)) {
		array_insert($macro_context, $i+1, 'exten => s,n,Set(item=${HANGUPCAUSE_KEYS()})');
//		array_insert($macro_context, $i+1, 'exten => s,n,DumpChan()');
		array_insert($macro_context, $i+2, 'exten => s,n,Set(DB(NUMBER/${ACTIONID}/cause)=${HANGUPCAUSE})');
		array_insert($macro_context, $i+3, 'exten => s,n,Set(DB(NUMBER/${ACTIONID}/sipcause)=${FILTER(0-9,${HANGUPCAUSE(${item},tech)})})');
// same => n,Verbose(0, Got Channel ID ${item} with Technology Cause Code ${HANGUPCAUSE(${item},tech)}, Asterisk Cause Code ${HANGUPCAUSE(${item},ast)})
		
		
		break;
	}
}

$contexts['macro-dialout-trunk-dialer'] = $macro_context;

echo contexts_plain($contexts);

