what it is right now

```
finds text file in same folder. 
recursively goes thru each line of the csv formated file
    searches youtube and other
    downloads audio using yt-dlp
    puts in folder selceted by user
    also scrapes as much meta data that can fit in mp3
```


what i want the process to be
```
finds text file in same folder. 
recursively goes thru each line of the csv formated file
    searches youtube and other
        search data base for song, 
            finds song
            takes meta data from that 
    downloads audio using yt-dlp
    puts in folder selceted by user
    also scrapes as much meta data that can fit in mp3

```

    use csv.DictReader
        switch between old format (2 keys) and new format (>2 keys)

        Push the song name and artist into the old songs list
        But keep the rest of the info in a metadata lookup thing

        Later when populating metadata, before searching the internet,
        if we have metadata from our fancy csv
        Use the fancy csv metadata first.
TODO
* ***bold+ilictac means important***
* also add compatibality for stuff like "My Spotify Library.csv"
* where there are more columns than normal
* have compatablity from the website https://www.tunemymusic.com/transfer and others like it
* which easly scraps playlists from websites like Spotify, or apple music
* for more specific searches use already popluated metadata
* Change so it only excepts CSV format, and if there is a txt file that look CSV have a question prompt that asks if it is CSV formated and if you would like to use that as a CSV and if so change that file from a .txt to a .CSV do checks to make sure that is still works and is formatted correctly. 
* if the header row looks like it is a song then suggest a change 
* ***HAVE it search other websites including stuff like gracenote or some song data base that leads to youtube videos to have it be more particluar than just choseing the first entry gotten back from youtube***




Notes ignore this stuff
```
Get the code to run to our area of change

See the variables, in a debugger or in a print statement



Write good logic

Use fancy variables to get data loaded

transform variables into new data

save new data


ETL 
Export Transform Load


{
    (title1, artist1) : {
        title :
        artist
        year
        ect
    }
}

[
    {title: title1, artist: artist1, "Track Title": title1, "Artist Name": artist1,year: 2017, },
    {title: title1, artist: artist1},
    {title: title1, artist: artist1},
    {title: title1, artist: artist1},
    {title: title1, artist: artist1},
    {title: title1, artist: artist1},
]



```











































