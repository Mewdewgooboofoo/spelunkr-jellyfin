
# Spelunkr for Jellyfin



An unofficial Spelunkr integration for Jellyfin Live TV. It provides an M3U playlist, an XMLTV programme guide, FFmpeg stream conversion and automatic updates to channel data from Spelunkr.



## Features



- M3U playlist for Jellyfin Live TV.

- XMLTV programme guide.

- FFmpeg stream conversion for playback.

- Automatic daily updates to channel and manifest data.

- Local caching of downloaded Spelunkr data.

- Channel data reloads without restarting the main service.



## Requirements



- Docker

- Docker Compose

- Jellyfin with network access to the Spelunkr service



## Installation



Clone the repository:



    git clone https://github.com/Mewdewgooboofoo/spelunkr-jellyfin.git

    cd spelunkr-jellyfin



The default service address is `http://192.168.1.141:8787`.



If your NAS uses a different address, create a `.env` file containing:



    BASE_URL=http://192.168.1.141:8787



Change the address to match your NAS if required.



Build and start the containers:



    sudo docker compose up -d --build



The updater runs when it starts and then repeats every 24 hours.



## Adding Spelunkr to Jellyfin



Open your Jellyfin web interface and sign in with an administrator account:



    http://192.168.1.141:8096/



### 1. Add the M3U tuner



1. Open the **Dashboard**.

2. Select **Live TV** from the server settings.

3. Find **Tuner Devices** and select the **+** button.

4. Set the tuner type to **M3U Tuner**.

5. Enter this address in the playlist URL field:



   `http://192.168.1.141:8787/playlist.m3u`



6. Leave the other options at their defaults initially.

7. Select **Save**.



Jellyfin will retrieve the playlist and scan the available channels.



### 2. Add the XMLTV programme guide



1. Stay in **Dashboard → Live TV**.

2. Find **TV Guide Data Providers** and select the **+** button.

3. Select **XMLTV**.

4. Enter this address in the URL field:



   `http://192.168.1.141:8787/guide.xml`



5. Select **Save**.



Jellyfin will retrieve the programme guide data.



### 3. Map channels to the programme guide



Jellyfin may not automatically match every channel to its guide listing.



1. In **Dashboard → Live TV**, find the XMLTV provider you added.

2. Open its **...** menu.

3. Select **Map Channels**, if available in your Jellyfin version.

4. Find a channel in the tuner list.

5. Select the edit option beside it.

6. Choose the matching channel from the guide provider.

7. Repeat for any channels that need mapping.



The playlist and guide use channel identifiers to help Jellyfin match listings. Check that the channel IDs correspond if a listing is missing.



### 4. Refresh the tuner and guide



If channels or programme listings do not appear:



1. Open **Dashboard → Live TV**.

2. Use the available refresh or rescan option for the tuner.

3. Refresh the guide data provider.

4. Allow Jellyfin time to retrieve the data.

5. Open **Live TV → Guide** and check the listings.



Jellyfin also refreshes guide data through its scheduled tasks.



### 5. Test playback



1. Open **Live TV → Channels** in Jellyfin.

2. Select a channel.

3. Allow time for the stream to start.



The first playback can take around two minutes while the stream is prepared.



## Service URLs



Using the default NAS address:



| Service | URL |

|---|---|

| M3U playlist | `http://192.168.1.141:8787/playlist.m3u` |

| XMLTV guide | `http://192.168.1.141:8787/guide.xml` |

| Service status | `http://192.168.1.141:8787/` |

| Jellyfin | `http://192.168.1.141:8096/` |



If you change the NAS address or Spelunkr service port, update the URLs in Jellyfin too.



## Automatic Updates



The updater container:



1. Retrieves the latest Spelunkr channel lineup.

2. Downloads the manifests referenced by the lineup.

3. Checks the downloaded data.

4. Installs the updated manifests.

5. Replaces the local lineup after the manifests have been installed.



The updater runs once at startup and then every 24 hours.



The main service checks for lineup changes and reloads its channel data when an update is detected.



## Docker Management



Start the services:



    sudo docker compose up -d



Stop the services:



    sudo docker compose down



Rebuild and restart the services:



    sudo docker compose up -d --build



View the main service logs:



    sudo docker logs -f spelunkr-jellyfin



View the updater logs:



    sudo docker logs -f spelunkr-updater



## Data and Backups



Downloaded Spelunkr data is stored in the `data` directory.



This directory is excluded from Git because the updater can download the data again. The repository includes an empty `data/.gitkeep` file so the directory is present after cloning.



Back up your Docker Compose configuration and any local changes you make. You do not need to commit downloaded manifests or other generated data.



## Troubleshooting



### Jellyfin cannot retrieve the playlist or guide



- Check that both Spelunkr containers are running.

- Open the playlist and guide URLs from another device on your network.

- Check that port `8787` is accessible on the NAS.

- If Jellyfin runs in Docker, use the NAS LAN IP rather than `localhost`.



### Channels appear but programme listings are missing



- Check that the XMLTV provider has been added.

- Refresh the guide data.

- Check the channel assignments.

- Check the main service logs for errors.



### A channel does not play



- Allow time for the stream to start.

- Check the main service logs.

- Check that the updater has downloaded the channel manifests.

- Playback depends on the availability of the upstream Spelunkr content.



## Attribution and Disclaimer



This is an unofficial community project and is not affiliated with or endorsed by Spelunkr or Jellyfin.



Spelunkr is the upstream source for channel and programme data. This project provides an integration layer for Jellyfin.



Use this project in accordance with the terms and rights applicable to the upstream content.

