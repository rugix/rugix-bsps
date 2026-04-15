# Rugix U-Boot boot script for A/B system updates with dedicated boot partitions.
#
# Partition layout (GPT):
#   1: config (FAT32)   — boot.scr, rugix.env
#   2: boot-a           — kernel, DTBs
#   3: boot-b           — kernel, DTBs
#   4: system-a         — root filesystem
#   5: system-b         — root filesystem
#   6: data             — persistent data
#
# Board-dependent values come from U-Boot environment:
#   ${devnum}   MMC device number
#   ${console}  Serial console
#   ${fdtfile}  Device tree blob filename

echo "Starting boot..."

mmc dev ${devnum}
mmc rescan

# Load persisted A/B state from the config partition.
if load mmc ${devnum}:1 ${loadaddr} rugix.env; then
  env import -c ${loadaddr} ${filesize}
else
  setenv rugix_state_dirty 1
fi

# First-boot defaults: boot group A (boot=2, system=4).
if test -z "${rugix_bootpart}"; then
  setenv rugix_boot_spare 0
  setenv rugix_bootpart 2
  setenv rugix_state_dirty 1
fi

echo "Boot Spare: " ${rugix_boot_spare}
echo "Bootpart: " ${rugix_bootpart}

# Determine which boot partition to use.
if test "${rugix_boot_spare}" = "1"; then
  if test "${rugix_bootpart}" = "3"; then
    setenv rugix_boot_part 2
  else
    setenv rugix_boot_part 3
  fi
  setenv rugix_boot_spare 0
  setenv rugix_state_dirty 1
else
  if test "${rugix_bootpart}" = "3"; then
    setenv rugix_boot_part 3
  else
    setenv rugix_boot_part 2
  fi
fi

# Derive the system partition: boot 2 → system 4, boot 3 → system 5.
setexpr rugix_sys_part ${rugix_boot_part} + 2

echo "Boot: mmc ${devnum}:${rugix_boot_part}  System: mmc ${devnum}:${rugix_sys_part}"

# Persist only when state actually changed.
if test -n "${rugix_state_dirty}"; then
  env export -c -s 0x4000 ${loadaddr} rugix_bootpart rugix_boot_spare
  fatwrite mmc ${devnum}:1 ${loadaddr} rugix.env 0x4000
fi

# Resolve PARTUUID for root= so it doesn't depend on device enumeration order.
part uuid mmc ${devnum}:${rugix_sys_part} rugix_root_uuid

setenv bootargs "root=PARTUUID=${rugix_root_uuid} rootwait init=/usr/bin/rugix-ctrl ro console=${console} panic=60"

# Load kernel and device tree from the selected boot partition.
load mmc ${devnum}:${rugix_boot_part} ${kernel_addr_r} Image
load mmc ${devnum}:${rugix_boot_part} ${fdt_addr_r} dtbs/${fdtfile}

booti ${kernel_addr_r} - ${fdt_addr_r}
