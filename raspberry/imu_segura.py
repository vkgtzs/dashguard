"""Lectura IMU con fallo explicito. No recupera ni recalibra automaticamente."""
import math
import time

CAMPOS=('ax_ms2','ay_ms2','az_ms2','magnitud_ms2','gx_grados_s','gy_grados_s','gz_grados_s')


def entero16(datos,inicio):
    valor=(datos[inicio]<<8)|datos[inicio+1]
    return valor-65536 if valor>=32768 else valor


class IMUSegura:
    def __init__(self,bus,direccion=0x68):
        self.bus=bus
        self.direccion=direccion
        self.offsets=None
        self.error='no_inicializada'

    def fallar(self,motivo):
        self.offsets=None
        self.error=motivo

    def bloque(self):
        if self.bus.read_byte_data(self.direccion,0x75)!=0x68:
            raise ValueError('identidad_inesperada')
        if self.bus.read_byte_data(self.direccion,0x6B)&0x40:
            raise ValueError('sensor_en_suspension')
        if (self.bus.read_byte_data(self.direccion,0x1B)&0x18 or
                self.bus.read_byte_data(self.direccion,0x1C)&0x18):
            raise ValueError('rangos_modificados')
        datos=self.bus.read_i2c_block_data(self.direccion,0x3B,14)
        if len(datos)!=14:
            raise ValueError('bloque_incompleto')
        if not any(datos):
            raise ValueError('bloque_en_cero')
        return datos

    def inicializar(self,muestras=500,esperar=time.sleep):
        try:
            self.bus.write_byte_data(self.direccion,0x6B,0)
            esperar(0.1)
            self.bus.write_byte_data(self.direccion,0x1B,0)
            self.bus.write_byte_data(self.direccion,0x1C,0)
            esperar(2)
            sumas=[0.,0.,0.]
            for _ in range(muestras):
                datos=self.bloque()
                for eje,inicio in enumerate((8,10,12)):
                    sumas[eje]+=entero16(datos,inicio)/131.
                esperar(0.01)
            self.offsets=[s/muestras for s in sumas]
            self.error=None
        except (OSError,ValueError) as error:
            self.fallar(str(error))

    def leer(self):
        if self.offsets is not None:
            try:
                datos=self.bloque()
                a=[entero16(datos,i)/16384.*9.80665 for i in (0,2,4)]
                g=[entero16(datos,i)/131.-self.offsets[e] for e,i in enumerate((8,10,12))]
                return dict(zip(CAMPOS,[*a,math.sqrt(sum(v*v for v in a)),*g]),
                            imu_valida=True,imu_error=None)
            except (OSError,ValueError) as error:
                self.fallar(str(error))
        return dict.fromkeys(CAMPOS,None)|dict(imu_valida=False,imu_error=self.error)
